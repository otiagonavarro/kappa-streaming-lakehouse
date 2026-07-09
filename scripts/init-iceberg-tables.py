#!/usr/bin/env python3
"""
Initialize Iceberg tables in Nessie catalog via PyFlink Table API.
Run after docker compose up — all services must be healthy.
"""
import os
from pyflink.table import EnvironmentSettings, TableEnvironment


def get_env(key, default=None):
    val = os.environ.get(key, default)
    if val is None:
        raise RuntimeError(f"Required env var {key} is not set")
    return val


def main():
    nessie_uri = get_env("NESSIE_URI", "http://localhost:19120/api/v1")
    storage_backend = get_env("STORAGE_BACKEND", "minio")
    minio_endpoint = get_env("MINIO_ENDPOINT", "http://localhost:9000")
    minio_access_key = get_env("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key = get_env("MINIO_SECRET_KEY", "minioadmin")
    minio_bucket = get_env("MINIO_BUCKET", "kappa-lake")
    gcs_bucket = get_env("GCS_BUCKET", "")

    if storage_backend == "gcs":
        warehouse = f"gs://{gcs_bucket}/warehouse"
    else:
        warehouse = f"s3://{minio_bucket}/warehouse"

    settings = EnvironmentSettings.in_batch_mode()
    env = TableEnvironment.create(settings)

    # Configure S3/MinIO or GCS filesystem
    if storage_backend == "minio":
        env.get_config().set("fs.s3a.endpoint", minio_endpoint)
        env.get_config().set("fs.s3a.access.key", minio_access_key)
        env.get_config().set("fs.s3a.secret.key", minio_secret_key)
        env.get_config().set("fs.s3a.path.style.access", "true")

    # Register Nessie + Iceberg catalog
    env.execute_sql(f"""
        CREATE CATALOG nessie_catalog WITH (
            'type'                  = 'iceberg',
            'catalog-type'          = 'nessie',
            'uri'                   = '{nessie_uri}',
            'ref'                   = 'main',
            'warehouse'             = '{warehouse}',
            'io-impl'               = 'org.apache.iceberg.aws.s3.S3FileIO',
            'client.region'         = 'us-east-1'
        )
    """)

    env.use_catalog("nessie_catalog")

    env.execute_sql("CREATE DATABASE IF NOT EXISTS kappa")
    env.use_database("kappa")

    env.execute_sql("""
        CREATE TABLE IF NOT EXISTS kappa.raw_events (
            event_id    STRING,
            event_type  STRING,
            user_id     STRING,
            session_id  STRING,
            product_id  STRING,
            `timestamp` TIMESTAMP(3),
            metadata    STRING,
            event_date  DATE
        )
        PARTITIONED BY (event_date)
        WITH (
            'format-version' = '2',
            'write.format.default' = 'parquet',
            'write.parquet.compression-codec' = 'snappy'
        )
    """)
    print("Created table: kappa.raw_events")

    env.execute_sql("""
        CREATE TABLE IF NOT EXISTS kappa.session_metrics (
            session_id               STRING,
            user_id                  STRING,
            session_start            TIMESTAMP(3),
            session_end              TIMESTAMP(3),
            session_duration_seconds BIGINT,
            event_count              INT,
            page_views               INT,
            add_to_carts             INT,
            purchases                INT,
            converted                BOOLEAN,
            session_date             DATE
        )
        PARTITIONED BY (session_date)
        WITH (
            'format-version' = '2',
            'write.format.default' = 'parquet',
            'write.parquet.compression-codec' = 'snappy'
        )
    """)
    print("Created table: kappa.session_metrics")
    print("Iceberg tables initialized successfully.")


if __name__ == "__main__":
    main()
