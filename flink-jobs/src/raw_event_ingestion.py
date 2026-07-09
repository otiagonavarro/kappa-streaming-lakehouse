"""
RawEventIngestionJob: Kafka → JSON deserialization → Iceberg kappa.raw_events

Exactly-once semantics via Flink checkpointing + Iceberg transactional commit.
"""
import click
from common import build_env, get_env


@click.command()
@click.option("--from-beginning", is_flag=True, default=False, help="Reset consumer group to earliest offset")
def main(from_beginning: bool):
    kafka_brokers = get_env("KAFKA_BROKERS", "localhost:9092")
    topic = "raw-events"
    group_id = "raw-event-ingestion"
    startup_mode = "earliest-offset" if from_beginning else "latest-offset"

    _, t_env = build_env()

    t_env.execute_sql("""
        CREATE TABLE IF NOT EXISTS kappa.raw_events (
            event_id    STRING,
            event_type  STRING,
            user_id     STRING,
            session_id  STRING,
            product_id  STRING,
            `timestamp` TIMESTAMP(6),
            metadata    STRING,
            event_date  DATE
        ) PARTITIONED BY (event_date)
        WITH (
            'format-version' = '2',
            'write.format.default' = 'parquet',
            'write.parquet.compression-codec' = 'snappy'
        )
    """)

    t_env.execute_sql(f"""
        CREATE TEMPORARY TABLE raw_events_source (
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
            'topic'                         = '{topic}',
            'properties.bootstrap.servers'  = '{kafka_brokers}',
            'properties.group.id'           = '{group_id}',
            'scan.startup.mode'             = '{startup_mode}',
            'format'                        = 'json',
            'json.fail-on-missing-field'    = 'false',
            'json.ignore-parse-errors'      = 'true'
        )
    """)

    t_env.execute_sql("""
        INSERT INTO kappa.raw_events
        SELECT
            event_id,
            event_type,
            user_id,
            session_id,
            product_id,
            TO_TIMESTAMP(`timestamp`, 'yyyy-MM-dd HH:mm:ss.SSS') AS `timestamp`,
            CAST(metadata AS STRING) AS metadata,
            CAST(TO_TIMESTAMP(`timestamp`, 'yyyy-MM-dd HH:mm:ss.SSS') AS DATE) AS event_date
        FROM raw_events_source
    """)


if __name__ == "__main__":
    main()
