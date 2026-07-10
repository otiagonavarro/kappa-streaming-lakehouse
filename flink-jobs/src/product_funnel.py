"""
ProductFunnelJob: Kafka → 1-minute tumbling windows → PostgreSQL product_funnel_1m

Counts page_view / add_to_cart / purchase per product per minute.
"""
import click # type: ignore
from common import build_env, get_env


@click.command()
@click.option("--from-beginning", is_flag=True, default=False, help="Reset consumer group to earliest offset")
@click.option("--window-minutes", default=1, type=int, help="Tumbling window size in minutes")
def main(from_beginning: bool, window_minutes: int):
    kafka_brokers = get_env("KAFKA_BROKERS", "localhost:9092")
    postgres_dsn = get_env("POSTGRES_DSN", "postgresql://kappa:kappa@localhost:5432/kappa")
    group_id = "product-funnel"
    startup_mode = "earliest-offset" if from_beginning else "latest-offset"

    jdbc_url = postgres_dsn.replace("postgresql://", "jdbc:postgresql://").split("@", 1)
    creds, host_db = jdbc_url[0].replace("jdbc:postgresql://", ""), jdbc_url[1]
    pg_user, pg_password = creds.split(":", 1)
    pg_jdbc = f"jdbc:postgresql://{host_db}"

    _, t_env = build_env()

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
            'connector'                      = 'kafka',
            'topic'                          = 'raw-events',
            'properties.bootstrap.servers'   = '{kafka_brokers}',
            'properties.group.id'            = '{group_id}',
            'scan.startup.mode'              = '{startup_mode}',
            'format'                         = 'json',
            'json.fail-on-missing-field'     = 'false',
            'json.ignore-parse-errors'       = 'true'
        )
    """)

    t_env.execute_sql(f"""
        CREATE TEMPORARY TABLE pg_product_funnel (
            product_id   STRING,
            window_start TIMESTAMP(3),
            window_end   TIMESTAMP(3),
            page_views   BIGINT,
            add_to_carts BIGINT,
            purchases    BIGINT,
            PRIMARY KEY (product_id, window_start) NOT ENFORCED
        ) WITH (
            'connector'   = 'jdbc',
            'url'         = '{pg_jdbc}',
            'table-name'  = 'product_funnel_1m',
            'username'    = '{pg_user}',
            'password'    = '{pg_password}',
            'sink.buffer-flush.max-rows' = '200',
            'sink.buffer-flush.interval' = '5s'
        )
    """)

    t_env.execute_sql(f"""
        INSERT INTO pg_product_funnel
        SELECT
            product_id,
            TUMBLE_START(`timestamp`, INTERVAL '{window_minutes}' MINUTE) AS window_start,
            TUMBLE_END(`timestamp`, INTERVAL '{window_minutes}' MINUTE) AS window_end,
            COUNT(CASE WHEN event_type = 'page_view'   THEN 1 END) AS page_views,
            COUNT(CASE WHEN event_type = 'add_to_cart' THEN 1 END) AS add_to_carts,
            COUNT(CASE WHEN event_type = 'purchase'    THEN 1 END) AS purchases
        FROM kafka_events
        GROUP BY product_id, TUMBLE(`timestamp`, INTERVAL '{window_minutes}' MINUTE)
    """)


if __name__ == "__main__":
    main()
