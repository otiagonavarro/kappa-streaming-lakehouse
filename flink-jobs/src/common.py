"""Shared config and catalog setup for all PyFlink jobs."""
import os
from pyflink.common import Configuration
from pyflink.datastream import StreamExecutionEnvironment, CheckpointingMode
from pyflink.table import StreamTableEnvironment


def get_env(key: str, default: str | None = None) -> str:
    val = os.environ.get(key, default)
    if val is None:
        raise RuntimeError(f"Required env var {key} is not set")
    return val


def build_env(checkpoint_interval_ms: int | None = None) -> tuple[StreamExecutionEnvironment, StreamTableEnvironment]:
    interval_ms = checkpoint_interval_ms or int(get_env("FLINK_CHECKPOINT_INTERVAL_MS", "30000"))
    storage_backend = get_env("STORAGE_BACKEND", "minio")
    minio_endpoint = get_env("MINIO_ENDPOINT", "http://localhost:9000")
    minio_access_key = get_env("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key = get_env("MINIO_SECRET_KEY", "minioadmin")
    minio_bucket = get_env("MINIO_BUCKET", "kappa-lake")
    gcs_bucket = get_env("GCS_BUCKET", "")
    nessie_uri = get_env("NESSIE_URI", "http://localhost:19120/api/v1")
    config = Configuration()

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
        config.set_string("fs.s3a.endpoint", minio_endpoint)
        config.set_string("fs.s3a.access.key", minio_access_key)
        config.set_string("fs.s3a.secret.key", minio_secret_key)
        config.set_string("fs.s3a.path.style.access", "true")
        # Iceberg 1.6+ removed catalog-type=nessie; use catalog-impl with explicit S3FileIO props
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

    env = StreamExecutionEnvironment.get_execution_environment(config)
    env.enable_checkpointing(interval_ms, CheckpointingMode.EXACTLY_ONCE)

    t_env = StreamTableEnvironment.create(env)
    t_env.execute_sql(catalog_sql)
    t_env.use_catalog("nessie_catalog")
    t_env.execute_sql("CREATE DATABASE IF NOT EXISTS kappa")
    t_env.use_database("kappa")

    return env, t_env
