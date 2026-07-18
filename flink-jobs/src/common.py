import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import yaml  # type: ignore
from pyflink.common import Configuration  # type: ignore
from pyflink.datastream import StreamExecutionEnvironment, CheckpointingMode  # type: ignore
from pyflink.table import StreamTableEnvironment  # type: ignore

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"


def get_env(key: str, default: str | None = None) -> str:
    val = os.environ.get(key, default)
    if val is None:
        raise RuntimeError(f"Required env var {key} is not set")
    return val


def load_contract(name: str) -> dict:
    """Load an ODCS data contract YAML from flink-jobs/contracts/<name>.contract.yaml."""
    path = CONTRACTS_DIR / f"{name}.contract.yaml"
    with path.open() as f:
        return yaml.safe_load(f)


def contract_server(contract: dict, server_type: str) -> dict:
    for server in contract["servers"]:
        if server["type"] == server_type:
            return server
    raise KeyError(f"No server of type '{server_type}' in contract {contract['id']}")


def contract_custom_property(contract: dict, key: str, default: str | None = None) -> str:
    for prop in contract.get("customProperties", []):
        if prop["property"] == key:
            return prop["value"]
    if default is not None:
        return default
    raise KeyError(f"customProperty '{key}' not found in contract {contract['id']}")


def kafka_source_ddl_from_contract(
    contract: dict,
    table_name: str,
    extra_columns_sql: str,
    kafka_brokers: str,
    group_id: str,
    startup_mode: str,
) -> str:
    """Build a Kafka source temp table DDL from a contract's kafka-type server entry.

    `extra_columns_sql` carries the staging columns (including watermark/proctime)
    that are specific to each job's read shape, not part of the contract's target schema.
    """
    source = contract_server(contract, "kafka")
    cfg = source.get("config", {})
    return f"""
        CREATE TEMPORARY TABLE {table_name} (
            {extra_columns_sql}
        ) WITH (
            'connector'                     = 'kafka',
            'topic'                         = '{source["topic"]}',
            'properties.bootstrap.servers'  = '{kafka_brokers}',
            'properties.group.id'           = '{group_id}',
            'scan.startup.mode'             = '{startup_mode}',
            'format'                        = '{source["format"]}',
            'json.fail-on-missing-field'    = '{cfg.get("json.fail-on-missing-field", "false")}',
            'json.ignore-parse-errors'      = '{cfg.get("json.ignore-parse-errors", "true")}'
        )
    """


def iceberg_sink_ddl_from_contract(contract: dict) -> str:
    """Build the Iceberg sink CREATE TABLE DDL entirely from the contract's schema + iceberg server."""
    table_schema = contract["schema"][0]
    sink = contract_server(contract, "iceberg")

    columns_sql = []
    partition_cols = []
    for prop in table_schema["properties"]:
        name = prop["name"]
        quoted = f"`{name}`" if name in ("timestamp",) else name
        columns_sql.append(f"{quoted} {prop['physicalType']}")
        if "partitionKeyPosition" in prop:
            partition_cols.append((prop["partitionKeyPosition"], name))
    partition_cols.sort(key=lambda x: x[0])

    partition_clause = ""
    if partition_cols:
        cols = ", ".join(name for _, name in partition_cols)
        partition_clause = f"PARTITIONED BY ({cols})"

    with_opts = ",\n            ".join(f"'{k}' = '{v}'" for k, v in sink["config"].items())
    columns_joined = ",\n            ".join(columns_sql)

    return f"""
        CREATE TABLE IF NOT EXISTS {table_schema['physicalName']} (
            {columns_joined}
        ) {partition_clause}
        WITH (
            {with_opts}
        )
    """


def get_polaris_token() -> str:
    token_url = get_env("POLARIS_TOKEN_URL", "http://localhost:8181/api/catalog/v1/oauth/tokens")
    client_id = get_env("POLARIS_CLIENT_ID", "root")
    client_secret = get_env("POLARIS_CLIENT_SECRET", "s3cr3t")
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "PRINCIPAL_ROLE:ALL",
    }).encode()
    req = urllib.request.Request(token_url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())
    return body["access_token"]


def create_databases(t_env: StreamTableEnvironment) -> None:
    for db in ("bronze", "silver", "gold"):
        t_env.execute_sql(f"CREATE DATABASE IF NOT EXISTS {db}")


def build_env(checkpoint_interval_ms: int | None = None) -> tuple[StreamExecutionEnvironment, StreamTableEnvironment]:
    interval_ms = checkpoint_interval_ms or int(get_env("FLINK_CHECKPOINT_INTERVAL_MS", "30000"))
    storage_backend = get_env("STORAGE_BACKEND", "minio")
    minio_endpoint = get_env("MINIO_ENDPOINT", "http://localhost:9000")
    minio_access_key = get_env("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key = get_env("MINIO_SECRET_KEY", "minioadmin")
    minio_bucket = get_env("MINIO_BUCKET", "kappa-lake")
    gcs_bucket = get_env("GCS_BUCKET", "")
    polaris_uri = get_env("POLARIS_URI", "http://localhost:8181/api/catalog")
    polaris_token = get_polaris_token()
    config = Configuration()

    if storage_backend == "gcs":
        warehouse = f"gs://{gcs_bucket}/warehouse"
        catalog_sql = f"""
            CREATE CATALOG polaris_catalog WITH (
                'type'                       = 'iceberg',
                'catalog-type'               = 'rest',
                'uri'                        = '{polaris_uri}',
                'warehouse'                  = '{warehouse}',
                'token'                      = '{polaris_token}',
                'rest.authorization.enabled'       = 'true',
                'rest.authorization.client-id'      = '{get_env("POLARIS_CLIENT_ID", "root")}',
                'rest.authorization.client-secret'  = '{get_env("POLARIS_CLIENT_SECRET", "s3cr3t")}',
                'rest.authorization.scope'          = 'PRINCIPAL_ROLE:ALL'
            )
        """
    else:
        warehouse = f"s3://{minio_bucket}/warehouse"
        config.set_string("fs.s3a.endpoint", minio_endpoint)
        config.set_string("fs.s3a.access.key", minio_access_key)
        config.set_string("fs.s3a.secret.key", minio_secret_key)
        config.set_string("fs.s3a.path.style.access", "true")
        catalog_sql = f"""
            CREATE CATALOG polaris_catalog WITH (
                'type'                   = 'iceberg',
                'catalog-type'           = 'rest',
                'uri'                    = '{polaris_uri}',
                'warehouse'              = '{warehouse}',
                'token'                      = '{polaris_token}',
                'rest.authorization.enabled'   = 'true',
                'rest.authorization.client-id' = '{get_env("POLARIS_CLIENT_ID", "root")}',
                'rest.authorization.client-secret' = '{get_env("POLARIS_CLIENT_SECRET", "s3cr3t")}',
                'rest.authorization.scope'          = 'PRINCIPAL_ROLE:ALL',
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
    t_env.use_catalog("polaris_catalog")
    create_databases(t_env)

    return env, t_env
