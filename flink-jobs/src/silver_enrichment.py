import click
from common import build_env, get_env
from contracts.loader import ddl_columns, partition_spec


@click.command()
@click.option("--from-beginning", is_flag=True, default=False, help="Reset consumer group to earliest offset")
def main(from_beginning: bool):
    kafka_brokers = get_env("KAFKA_BROKERS", "localhost:9092")
    group_id = "silver-enrichment"
    startup_mode = "earliest-offset" if from_beginning else "latest-offset"

    env, t_env = build_env()

    t_env.execute_sql(f"""
        CREATE TABLE IF NOT EXISTS silver.validated_events (
            {ddl_columns("silver", "validated_events")}
        ) {partition_spec("silver", "validated_events")}
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
            `timestamp` STRING,
            metadata    STRING,
            proctime    AS PROCTIME()
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

    t_env.execute_sql("""
        INSERT INTO silver.validated_events
        SELECT
            event_id,
            event_type,
            user_id,
            session_id,
            product_id,
            TO_TIMESTAMP(`timestamp`, 'yyyy-MM-dd HH:mm:ss.SSS') AS event_timestamp,
            CAST(metadata AS STRING) AS metadata,
            CAST(TO_TIMESTAMP(`timestamp`, 'yyyy-MM-dd HH:mm:ss.SSS') AS DATE) AS event_date,
            CAST(JSON_VALUE(metadata, '$.page') AS STRING) AS page_url,
            CAST(JSON_VALUE(metadata, '$.referrer') AS STRING) AS referrer,
            PROCTIME() AS ingestion_ts
        FROM kafka_events
        WHERE
            event_id IS NOT NULL
            AND event_type IN ('page_view', 'add_to_cart', 'purchase')
            AND user_id IS NOT NULL
            AND session_id IS NOT NULL
    """)

    print("Silver enrichment pipeline running. Validates and enriches raw events into silver.validated_events.")


if __name__ == "__main__":
    main()
