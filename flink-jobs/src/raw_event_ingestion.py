"""
RawEventIngestionJob: Kafka → JSON deserialization → Iceberg kappa.raw_events

Topic, target table schema, and storage properties come from the ODCS data contract
at flink-jobs/contracts/raw_events.contract.yaml (see common.load_contract) — this
job is a generic executor of that contract, not the source of truth for it.

Exactly-once semantics via Flink checkpointing + Iceberg transactional commit.
"""
import click # type: ignore
from common import (
    build_env,
    get_env,
    iceberg_sink_ddl_from_contract,
    kafka_source_ddl_from_contract,
    load_contract,
)


@click.command()
@click.option("--from-beginning", is_flag=True, default=False, help="Reset consumer group to earliest offset")
def main(from_beginning: bool):
    contract = load_contract("raw_events")
    kafka_brokers = get_env("KAFKA_BROKERS", "localhost:9092")
    group_id = contract["servers"][0]["config"]["properties.group.id"]
    startup_mode = "earliest-offset" if from_beginning else "latest-offset"

    _, t_env = build_env()

    t_env.execute_sql(iceberg_sink_ddl_from_contract(contract))

    t_env.execute_sql(
        kafka_source_ddl_from_contract(
            contract,
            table_name="raw_events_source",
            extra_columns_sql="""
            event_id    STRING,
            event_type  STRING,
            user_id     STRING,
            session_id  STRING,
            product_id  STRING,
            `timestamp` STRING,
            metadata    STRING,
            proctime    AS PROCTIME()""",
            kafka_brokers=kafka_brokers,
            group_id=group_id,
            startup_mode=startup_mode,
        )
    )

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
