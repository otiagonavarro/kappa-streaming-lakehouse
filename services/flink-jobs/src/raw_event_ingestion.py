"""
RawEventIngestionJob: Kafka → JSON deserialization → Iceberg bronze.raw_events

Target table schema and partitioning come from the ODCS data contract at
contracts/bronze/raw_events.yaml (see contracts.loader) — this job is a generic
executor of that contract, not the source of truth for it.

Exactly-once semantics via Flink checkpointing + Iceberg transactional commit.
"""
import click  # type: ignore
from common import build_env, get_env
from contracts.loader import ddl_columns, partition_spec


@click.command()
@click.option("--from-beginning", is_flag=True, default=False, help="Reset consumer group to earliest offset")
def main(from_beginning: bool):
    kafka_brokers = get_env("KAFKA_BROKERS", "localhost:9092")
    group_id = "raw-event-ingestion"
    startup_mode = "earliest-offset" if from_beginning else "latest-offset"

    env, t_env = build_env()

    t_env.execute_sql(f"""
        CREATE TABLE IF NOT EXISTS bronze.raw_events (
            {ddl_columns("bronze", "raw_events")}
        ) {partition_spec("bronze", "raw_events")}
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
        INSERT INTO bronze.raw_events
        SELECT
            event_id,
            event_type,
            user_id,
            session_id,
            product_id,
            TO_TIMESTAMP(`timestamp`, 'yyyy-MM-dd HH:mm:ss.SSS') AS event_timestamp,
            CAST(metadata AS STRING) AS metadata,
            CAST(TO_TIMESTAMP(`timestamp`, 'yyyy-MM-dd HH:mm:ss.SSS') AS DATE) AS event_date
        FROM raw_events_source
    """)

    print("Bronze ingestion pipeline running. Use --from-beginning to replay from earliest offset.")


if __name__ == "__main__":
    main()
