"""
OrderIngestionJob: Kafka (entity-updates) → Iceberg + PostgreSQL order fact tables

Ingests orders and order_items from the entity-updates CDC topic
to both the Iceberg lakehouse (durable history) and PostgreSQL (serving).
"""
import click  # type: ignore
from common import build_env, get_env


@click.command()
@click.option("--from-beginning", is_flag=True, default=False, help="Reset consumer group to earliest offset")
def main(from_beginning: bool):
    kafka_brokers = get_env("KAFKA_BROKERS", "localhost:9092")
    postgres_dsn = get_env("POSTGRES_DSN", "postgresql://kappa:kappa@localhost:5432/kappa")
    entity_topic = get_env("SIMULATOR_ENTITY_TOPIC", "entity-updates")
    group_id = "order-ingestion"
    startup_mode = "earliest-offset" if from_beginning else "latest-offset"

    # Parse DSN for JDBC URL
    jdbc_url = postgres_dsn.replace("postgresql://", "jdbc:postgresql://").split("@", 1)
    creds, host_db = jdbc_url[0].replace("jdbc:postgresql://", ""), jdbc_url[1]
    pg_user, pg_password = creds.split(":", 1)
    pg_jdbc = f"jdbc:postgresql://{host_db}"

    _, t_env = build_env()

    # ── Iceberg fact tables ──────────────────────────────────────────────────

    t_env.execute_sql("""
        CREATE TABLE IF NOT EXISTS kappa.orders (
            order_id    STRING,
            user_id     STRING,
            total       DECIMAL(10, 2),
            status      STRING,
            created_at  TIMESTAMP(6),
            order_date  DATE
        )
        PARTITIONED BY (order_date)
        WITH (
            'format-version' = '2',
            'write.format.default' = 'parquet',
            'write.parquet.compression-codec' = 'snappy'
        )
    """)

    t_env.execute_sql("""
        CREATE TABLE IF NOT EXISTS kappa.order_items (
            order_item_id  STRING,
            order_id       STRING,
            product_id     STRING,
            quantity       INT,
            unit_price     DECIMAL(10, 2),
            line_total     DECIMAL(10, 2),
            order_date     DATE
        )
        PARTITIONED BY (order_date)
        WITH (
            'format-version' = '2',
            'write.format.default' = 'parquet',
            'write.parquet.compression-codec' = 'snappy'
        )
    """)

    # ── Kafka source (wide schema — shared with entity_sync) ─────────────────

    t_env.execute_sql(f"""
        CREATE TEMPORARY TABLE kafka_entity_updates (
            entity_type       STRING,
            order_id          STRING,
            order_user_id     STRING,
            order_total       DECIMAL(10, 2),
            order_status      STRING,
            order_created_at  TIMESTAMP(3),
            order_date        DATE,
            order_item_id     STRING,
            order_item_order_id STRING,
            product_id        STRING,
            quantity          INT,
            unit_price        DECIMAL(10, 2),
            line_total        DECIMAL(10, 2)
        ) WITH (
            'connector'                     = 'kafka',
            'topic'                         = '{entity_topic}',
            'properties.bootstrap.servers'  = '{kafka_brokers}',
            'properties.group.id'           = '{group_id}',
            'scan.startup.mode'             = '{startup_mode}',
            'format'                        = 'json',
            'json.fail-on-missing-field'    = 'false',
            'json.ignore-parse-errors'      = 'true'
        )
    """)

    # ── Iceberg INSERTs ──────────────────────────────────────────────────────

    t_env.execute_sql("""
        INSERT INTO kappa.orders
        SELECT
            order_id,
            order_user_id,
            order_total,
            order_status,
            order_created_at,
            order_date
        FROM kafka_entity_updates
        WHERE entity_type = 'order'
    """)

    t_env.execute_sql("""
        INSERT INTO kappa.order_items
        SELECT
            order_item_id,
            order_item_order_id,
            product_id,
            quantity,
            unit_price,
            line_total,
            order_date
        FROM kafka_entity_updates
        WHERE entity_type = 'order_item'
    """)

    # ── PostgreSQL JDBC sinks ────────────────────────────────────────────────

    t_env.execute_sql(f"""
        CREATE TEMPORARY TABLE pg_orders (
            order_id    STRING,
            user_id     STRING,
            total       DECIMAL(10, 2),
            status      STRING,
            created_at  TIMESTAMP(3),
            order_date  DATE,
            PRIMARY KEY (order_id) NOT ENFORCED
        ) WITH (
            'connector'   = 'jdbc',
            'url'         = '{pg_jdbc}',
            'table-name'  = 'orders',
            'username'    = '{pg_user}',
            'password'    = '{pg_password}',
            'sink.buffer-flush.max-rows' = '100',
            'sink.buffer-flush.interval' = '2s'
        )
    """)

    t_env.execute_sql(f"""
        CREATE TEMPORARY TABLE pg_order_items (
            order_item_id  STRING,
            order_id       STRING,
            product_id     STRING,
            quantity       INT,
            unit_price     DECIMAL(10, 2),
            line_total     DECIMAL(10, 2),
            order_date     DATE,
            PRIMARY KEY (order_item_id) NOT ENFORCED
        ) WITH (
            'connector'   = 'jdbc',
            'url'         = '{pg_jdbc}',
            'table-name'  = 'order_items',
            'username'    = '{pg_user}',
            'password'    = '{pg_password}',
            'sink.buffer-flush.max-rows' = '200',
            'sink.buffer-flush.interval' = '5s'
        )
    """)

    # ── PostgreSQL INSERTs ───────────────────────────────────────────────────

    t_env.execute_sql("""
        INSERT INTO pg_orders
        SELECT
            order_id,
            order_user_id,
            order_total,
            order_status,
            order_created_at,
            order_date
        FROM kafka_entity_updates
        WHERE entity_type = 'order'
    """)

    t_env.execute_sql("""
        INSERT INTO pg_order_items
        SELECT
            order_item_id,
            order_item_order_id,
            product_id,
            quantity,
            unit_price,
            line_total,
            order_date
        FROM kafka_entity_updates
        WHERE entity_type = 'order_item'
    """)


if __name__ == "__main__":
    main()
