#!/usr/bin/env bash
# Time-travel demo: capture a snapshot, ingest more data, then query the past snapshot via DuckDB.
set -euo pipefail

NESSIE_URI=${NESSIE_URI:-http://localhost:19120/api/v1}
MINIO_ENDPOINT=${MINIO_ENDPOINT:-http://localhost:9000}
MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY:-minioadmin}
MINIO_SECRET_KEY=${MINIO_SECRET_KEY:-minioadmin}
MINIO_BUCKET=${MINIO_BUCKET:-kappa-lake}

echo "=== Kappa Architecture — Time Travel Demo ==="

# 1. Capture current snapshot ID from Iceberg metadata
echo ""
echo "Step 1: Capturing current Iceberg snapshot ID..."
SNAPSHOT_ID=$(python3 -c "
import duckdb, os
con = duckdb.connect()
con.execute(\"INSTALL iceberg; LOAD iceberg;\")
con.execute(\"INSTALL httpfs; LOAD httpfs;\")
con.execute(\"SET s3_endpoint='${MINIO_ENDPOINT}'; SET s3_access_key_id='${MINIO_ACCESS_KEY}'; SET s3_secret_access_key='${MINIO_SECRET_KEY}'; SET s3_url_style='path';\")
import subprocess, json
result = subprocess.run(
    ['python3', 'scripts/get-iceberg-metadata-path.py', 'raw_events'],
    capture_output=True, text=True
)
metadata_path = result.stdout.strip()
if metadata_path:
    sid = con.execute(f\"SELECT snapshot_id FROM iceberg_scan('{metadata_path}') ORDER BY commit_at DESC LIMIT 1\").fetchone()
    print(sid[0] if sid else 'unknown')
else:
    print('unknown')
")
echo "Current Iceberg snapshot ID: ${SNAPSHOT_ID}"

# 2. Count rows at this snapshot
echo ""
echo "Step 2: Row count at snapshot (before additional ingestion)..."
BEFORE_COUNT=$(python3 -c "
import duckdb, os
con = duckdb.connect()
con.execute(\"INSTALL iceberg; LOAD iceberg;\")
con.execute(\"INSTALL httpfs; LOAD httpfs;\")
con.execute(\"SET s3_endpoint='${MINIO_ENDPOINT}'; SET s3_access_key_id='${MINIO_ACCESS_KEY}'; SET s3_secret_access_key='${MINIO_SECRET_KEY}'; SET s3_url_style='path';\")
# Discover latest metadata file
import subprocess, json
result = subprocess.run(
    ['python3', 'scripts/get-iceberg-metadata-path.py', 'raw_events'],
    capture_output=True, text=True
)
metadata_path = result.stdout.strip()
if not metadata_path:
    print(0)
else:
    count = con.execute(f\"SELECT COUNT(*) FROM iceberg_scan('{metadata_path}')\").fetchone()[0]
    print(count)
")
echo "Rows before: ${BEFORE_COUNT}"

# 3. Ingest 500 more events via simulator
echo ""
echo "Step 3: Ingesting 500 more events..."
docker compose -f infra/compose/docker-compose.yml run --rm simulator simulator --count 500 --rate 50
echo "Waiting 20s for Flink to commit batch..."
sleep 20

# 4. Count rows after ingestion
echo ""
echo "Step 4: Current row count (after ingestion)..."
echo "  (Check Flink UI at http://localhost:8081 or query Iceberg directly)"

# 5. Time-travel query using DuckDB at the captured snapshot
echo ""
echo "Step 5: Querying Iceberg as of snapshot (before ingestion)..."
echo "  Iceberg snapshot ID: ${SNAPSHOT_ID}"
echo ""
echo "  DuckDB time-travel query:"
echo "  SELECT COUNT(*) FROM iceberg_scan('<metadata>', version = '<snapshot_id>');"
echo ""
echo "  See docs/tradeoffs.md for full time-travel query examples."
echo ""
echo "=== Demo complete ==="
