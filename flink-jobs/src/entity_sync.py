"""
EntitySyncJob: Kafka (entity-updates) → Iceberg + PostgreSQL dimension tables

Syncs users, products, and categories from the entity-updates CDC topic
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
    group_id = "entity-sync"
    startup_mode = "earliest-offset" if from_beginning else "latest-offset"

    # Parse DSN for JDBC URL
    jdbc_url = postgres_dsn.replace("postgresql://", "jdbc:postgresql://").split("@", 1)
    creds, host_db = jdbc_url[0].replace("jdbc:postgresql://", ""), jdbc_url[1]
    pg_user, pg_password = creds.split(":", 1)
    pg_jdbc = f"jdbc:postgresql://{host_db}"

    _, t_env = build_env()

    # ── Iceberg dimension tables ─────────────────────────────────────────────

    t_env.execute_sql("""
        CREATE TABLE IF NOT EXISTS kappa.categories (
            category_id         STRING,
            name                STRING,
            parent_category_id  STRING
        )
        WITH (
            'format-version' = '2',
            'write.format.default' = 'parquet',
            'write.parquet.compression-codec' = 'snappy'
        )
    """)

    t_env.execute_sql("""
        CREATE TABLE IF NOT EXISTS kappa.users (
            user_id          STRING,
            name             STRING,
            email            STRING,
            city             STRING,
            registered_date  DATE,
            status           STRING,
            updated_at       TIMESTAMP(6)
        )
        PARTITIONED BY (registered_date)
        WITH (
            'format-version' = '2',
            'write.format.default' = 'parquet',
            'write.parquet.compression-codec' = 'snappy'
        )
    """)

    t_env.execute_sql("""
        CREATE TABLE IF NOT EXISTS kappa.products (
            product_id    STRING,
            name          STRING,
            category_id   STRING,
            price         DECIMAL(10, 2),
            status        STRING,
            created_at    TIMESTAMP(6)
        )
        PARTITIONED BY (category_id)
        WITH (
            'format-version' = '2',
            'write.format.default' = 'parquet',
            'write.parquet.compression-codec' = 'snappy'
        )
    """)

    # ── Kafka source (wide schema — all fields nullable) ─────────────────────

    t_env.execute_sql(f"""
        CREATE TEMPORARY TABLE kafka_entity_updates (
            entity_type       STRING,
            user_id           STRING,
            user_name         STRING,
            user_email        STRING,
            user_city         STRING,
            registered_date   DATE,
            user_status       STRING,
            product_id        STRING,
            product_name      STRING,
            category_id       STRING,
            price             DECIMAL(10, 2),
            product_status    STRING,
            cat_name          STRING,
            parent_category_id STRING,
            created_at        TIMESTAMP(3),
            updated_at        TIMESTAMP(3)
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
        INSERT INTO kappa.categories
        SELECT
            category_id,
            cat_name,
            parent_category_id
        FROM kafka_entity_updates
        WHERE entity_type = 'category'
    """)

    t_env.execute_sql("""
        INSERT INTO kappa.users
        SELECT
            user_id,
            user_name,
            user_email,
            user_city,
            registered_date,
            user_status,
            updated_at
        FROM kafka_entity_updates
        WHERE entity_type = 'user'
    """)

    t_env.execute_sql("""
        INSERT INTO kappa.products
        SELECT
            product_id,
            product_name,
            category_id,
            price,
            product_status,
            created_at
        FROM kafka_entity_updates
        WHERE entity_type = 'product'
    """)

    # ── PostgreSQL JDBC sinks ────────────────────────────────────────────────

    t_env.execute_sql(f"""
        CREATE TEMPORARY TABLE pg_categories (
            category_id         STRING,
            name                STRING,
            parent_category_id  STRING,
            PRIMARY KEY (category_id) NOT ENFORCED
        ) WITH (
            'connector'   = 'jdbc',
            'url'         = '{pg_jdbc}',
            'table-name'  = 'categories',
            'username'    = '{pg_user}',
            'password'    = '{pg_password}',
            'sink.buffer-flush.max-rows' = '100',
            'sink.buffer-flush.interval' = '2s'
        )
    """)

    t_env.execute_sql(f"""
        CREATE TEMPORARY TABLE pg_users (
            user_id          STRING,
            name             STRING,
            email            STRING,
            city             STRING,
            registered_date  DATE,
            status           STRING,
            PRIMARY KEY (user_id) NOT ENFORCED
        ) WITH (
            'connector'   = 'jdbc',
            'url'         = '{pg_jdbc}',
            'table-name'  = 'users',
            'username'    = '{pg_user}',
            'password'    = '{pg_password}',
            'sink.buffer-flush.max-rows' = '100',
            'sink.buffer-flush.interval' = '2s'
        )
    """)

    t_env.execute_sql(f"""
        CREATE TEMPORARY TABLE pg_products (
            product_id    STRING,
            name          STRING,
            category_id   STRING,
            price         DECIMAL(10, 2),
            status        STRING,
            PRIMARY KEY (product_id) NOT ENFORCED
        ) WITH (
            'connector'   = 'jdbc',
            'url'         = '{pg_jdbc}',
            'table-name'  = 'products',
            'username'    = '{pg_user}',
            'password'    = '{pg_password}',
            'sink.buffer-flush.max-rows' = '100',
            'sink.buffer-flush.interval' = '2s'
        )
    """)

    # ── PostgreSQL INSERTs ───────────────────────────────────────────────────

    t_env.execute_sql("""
        INSERT INTO pg_categories
        SELECT
            category_id,
            cat_name,
            parent_category_id
        FROM kafka_entity_updates
        WHERE entity_type = 'category'
    """)

    t_env.execute_sql("""
        INSERT INTO pg_users
        SELECT
            user_id,
            user_name,
            user_email,
            user_city,
            registered_date,
            user_status
        FROM kafka_entity_updates
        WHERE entity_type = 'user'
    """)

    t_env.execute_sql("""
        INSERT INTO pg_products
        SELECT
            product_id,
            product_name,
            category_id,
            price,
            product_status
        FROM kafka_entity_updates
        WHERE entity_type = 'product'
    """)


if __name__ == "__main__":
    main()
