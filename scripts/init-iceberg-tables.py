#!/usr/bin/env python3
"""
Initialize Iceberg tables across bronze/silver/gold layers via Project Nessie.
Schemas are driven by ODCS contracts in contracts/.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "flink-jobs", "src"))

from pyflink.table import EnvironmentSettings, TableEnvironment  # noqa: E402
from contracts.loader import ddl_columns, partition_spec  # noqa: E402  # pyright: ignore[reportMissingImports]


def get_env(key, default=None):
    val = os.environ.get(key, default)
    if val is None:
        raise RuntimeError(f"Required env var {key} is not set")
    return val


TABLE_SPECS = [
    ("bronze", "raw_events"),
    ("silver", "validated_events"),
    ("silver", "user_sessions"),
    ("gold", "session_metrics"),
    ("gold", "product_funnel_1m"),
    ("gold", "user_360"),
]


def main():
    nessie_uri = get_env("NESSIE_URI", "http://localhost:19120/api/v1")
    storage_backend = get_env("STORAGE_BACKEND", "minio")
    minio_endpoint = get_env("MINIO_ENDPOINT", "http://localhost:9000")
    minio_access_key = get_env("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key = get_env("MINIO_SECRET_KEY", "minioadmin")
    minio_bucket = get_env("MINIO_BUCKET", "kappa-lake")
    gcs_bucket = get_env("GCS_BUCKET", "")

    settings = EnvironmentSettings.in_batch_mode()
    env = TableEnvironment.create(settings)

    if storage_backend == "gcs":
        warehouse = f"gs://{gcs_bucket}/warehouse"
        catalog_sql = f"""
            CREATE CATALOG nessie_catalog WITH (
                'type'         = 'iceberg',
                'catalog-impl' = 'org.apache.iceberg.nessie.NessieCatalog',
                'uri'          = '{nessie_uri}',
                'ref'          = 'main',
                'warehouse'    = '{warehouse}'
            )
        """
    else:
        warehouse = f"s3://{minio_bucket}/warehouse"
        env.get_config().set("fs.s3a.endpoint", minio_endpoint)
        env.get_config().set("fs.s3a.access.key", minio_access_key)
        env.get_config().set("fs.s3a.secret.key", minio_secret_key)
        env.get_config().set("fs.s3a.path.style.access", "true")
        catalog_sql = f"""
            CREATE CATALOG nessie_catalog WITH (
                'type'                   = 'iceberg',
                'catalog-impl'           = 'org.apache.iceberg.nessie.NessieCatalog',
                'uri'                    = '{nessie_uri}',
                'ref'                    = 'main',
                'warehouse'              = '{warehouse}',
                'io-impl'                = 'org.apache.iceberg.aws.s3.S3FileIO',
                's3.endpoint'            = '{minio_endpoint}',
                's3.access-key-id'       = '{minio_access_key}',
                's3.secret-access-key'   = '{minio_secret_key}',
                's3.path-style-access'   = 'true',
                'client.region'          = 'us-east-1'
            )
        """

    env.execute_sql(catalog_sql)
    env.use_catalog("nessie_catalog")

    for db in ("bronze", "silver", "gold"):
        env.execute_sql(f"CREATE DATABASE IF NOT EXISTS {db}")

    for layer, table in TABLE_SPECS:
        ddl = ddl_columns(layer, table)
        part = partition_spec(layer, table)
        env.execute_sql(f"""
            CREATE TABLE IF NOT EXISTS {layer}.{table} (
                {ddl}
            ) {part}
            WITH (
                'format-version' = '2',
                'write.format.default' = 'parquet',
                'write.parquet.compression-codec' = 'snappy'
            )
        """)
        print(f"Ensured table: {layer}.{table}")

    print("All Iceberg tables initialized across bronze/silver/gold layers.")


if __name__ == "__main__":
    main()
