"""
SessionAggregationJob: Kafka → session windows (30-min gap) → Iceberg + PostgreSQL

Dual sink: durable history in Iceberg, low-latency serving in PostgreSQL (upsert).
"""
import click  # type: ignore
from common import build_env, get_env
from contracts.loader import ddl_columns, partition_spec


@click.command()
@click.option("--from-beginning", is_flag=True, default=False, help="Reset consumer group to earliest offset")
@click.option("--session-gap-minutes", default=30, type=int, help="Session gap timeout in minutes")
def main(from_beginning: bool, session_gap_minutes: int):
    kafka_brokers = get_env("KAFKA_BROKERS", "localhost:9092")
    postgres_dsn = get_env("POSTGRES_DSN", "postgresql://kappa:kappa@localhost:5432/kappa")
    group_id = "session-aggregation"
    startup_mode = "earliest-offset" if from_beginning else "latest-offset"

    jdbc_url = postgres_dsn.replace("postgresql://", "jdbc:postgresql://").split("@", 1)
    creds, host_db = jdbc_url[0].replace("jdbc:postgresql://", ""), jdbc_url[1]
    pg_user, pg_password = creds.split(":", 1)
    pg_jdbc = f"jdbc:postgresql://{host_db}"

    env, t_env = build_env()

    t_env.execute_sql(f"""
        CREATE TABLE IF NOT EXISTS gold.session_metrics (
            {ddl_columns("gold", "session_metrics")}
        ) {partition_spec("gold", "session_metrics")}
        WITH (
            'format-version' = '2',
            'write.format.default' = 'parquet',
            'write.parquet.compression-codec' = 'snappy'
        )
    """)

    t_env.execute_sql(f"""
        CREATE TABLE IF NOT EXISTS silver.user_sessions (
            {ddl_columns("silver", "user_sessions")}
        ) {partition_spec("silver", "user_sessions")}
        WITH (
            'format-version' = '2',
            'write.format.default' = 'parquet',
            'write.parquet.compression-codec' = 'snappy'
        )
    """)

    t_env.execute_sql(f"""
        CREATE TEMPORARY TABLE kafka_events (
            event_id    STRING,
            event_type  STRING,
            user_id     STRING,
            session_id  STRING,
            product_id  STRING,
            `timestamp` TIMESTAMP(3),
            WATERMARK FOR `timestamp` AS `timestamp` - INTERVAL '5' SECOND
        ) WITH (
            'connector'                     = 'kafka',
            'topic'                         = 'raw-events',
            'properties.bootstrap.servers'  = '{kafka_brokers}',
            'properties.group.id'           = '{group_id}',
            'scan.startup.mode'             = '{startup_mode}',
            'format'                        = 'json',
            'json.fail-on-missing-field'    = 'false',
            'json.ignore-parse-errors'      = 'true'
        )
    """)

    gap_interval = f"INTERVAL '{session_gap_minutes}' MINUTE"

    t_env.execute_sql(f"""
        INSERT INTO silver.user_sessions
        SELECT
            session_id,
            user_id,
            SESSION_START(`timestamp`, {gap_interval}) AS session_start,
            SESSION_END(`timestamp`, {gap_interval}) AS session_end,
            COUNT(*) AS event_count,
            CAST(SESSION_START(`timestamp`, {gap_interval}) AS DATE) AS session_date
        FROM kafka_events
        GROUP BY session_id, user_id, SESSION(`timestamp`, {gap_interval})
    """)

    t_env.execute_sql(f"""
        INSERT INTO gold.session_metrics
        SELECT
            session_id,
            user_id,
            SESSION_START(`timestamp`, {gap_interval}) AS session_start,
            SESSION_END(`timestamp`, {gap_interval}) AS session_end,
            TIMESTAMPDIFF(SECOND,
                SESSION_START(`timestamp`, {gap_interval}),
                SESSION_END(`timestamp`, {gap_interval})) AS session_duration_seconds,
            COUNT(*) AS event_count,
            COUNT(CASE WHEN event_type = 'page_view'   THEN 1 END) AS page_views,
            COUNT(CASE WHEN event_type = 'add_to_cart' THEN 1 END) AS add_to_carts,
            COUNT(CASE WHEN event_type = 'purchase'    THEN 1 END) AS purchases,
            COUNT(CASE WHEN event_type = 'purchase' THEN 1 END) > 0 AS converted,
            CAST(SESSION_START(`timestamp`, {gap_interval}) AS DATE) AS session_date
        FROM kafka_events
        GROUP BY session_id, user_id, SESSION(`timestamp`, {gap_interval})
    """)

    t_env.execute_sql(f"""
        CREATE TEMPORARY TABLE pg_session_metrics (
            session_id               STRING,
            user_id                  STRING,
            session_date             DATE,
            session_start            TIMESTAMP(3),
            session_end              TIMESTAMP(3),
            session_duration_seconds BIGINT,
            event_count              INT,
            page_views               INT,
            add_to_carts             INT,
            purchases                INT,
            converted                BOOLEAN,
            PRIMARY KEY (session_id) NOT ENFORCED
        ) WITH (
            'connector'   = 'jdbc',
            'url'         = '{pg_jdbc}',
            'table-name'  = 'session_metrics',
            'username'    = '{pg_user}',
            'password'    = '{pg_password}',
            'sink.buffer-flush.max-rows' = '100',
            'sink.buffer-flush.interval' = '2s'
        )
    """)

    t_env.execute_sql(f"""
        INSERT INTO pg_session_metrics
        SELECT
            session_id,
            user_id,
            CAST(SESSION_START(`timestamp`, {gap_interval}) AS DATE),
            SESSION_START(`timestamp`, {gap_interval}),
            SESSION_END(`timestamp`, {gap_interval}),
            CAST(TIMESTAMPDIFF(SECOND,
                SESSION_START(`timestamp`, {gap_interval}),
                SESSION_END(`timestamp`, {gap_interval})) AS BIGINT),
            CAST(COUNT(*) AS INT),
            CAST(COUNT(CASE WHEN event_type = 'page_view'   THEN 1 END) AS INT),
            CAST(COUNT(CASE WHEN event_type = 'add_to_cart' THEN 1 END) AS INT),
            CAST(COUNT(CASE WHEN event_type = 'purchase'    THEN 1 END) AS INT),
            COUNT(CASE WHEN event_type = 'purchase' THEN 1 END) > 0
        FROM kafka_events
        GROUP BY session_id, user_id, SESSION(`timestamp`, {gap_interval})
    """)


if __name__ == "__main__":
    main()
