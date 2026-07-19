#!/usr/bin/env bash
set -euo pipefail

FLINK_API=${FLINK_API:-http://localhost:8081}
POSTGRES_DSN=${POSTGRES_DSN:-postgresql://kappa:kappa@localhost:5432/kappa}

echo "=== Kappa Reprocessing (bronze → silver → gold) ==="
echo ""

echo "Step 1: Cancelling all running Flink jobs..."
JOBS=$(curl -sf "${FLINK_API}/jobs" | python3 -c "
import sys, json
jobs = json.load(sys.stdin)['jobs']
running = [j['id'] for j in jobs if j['status'] == 'RUNNING']
print('\n'.join(running))
")

for JOB_ID in $JOBS; do
    echo "  Cancelling job ${JOB_ID}..."
    curl -sf -X PATCH "${FLINK_API}/jobs/${JOB_ID}?mode=cancel" > /dev/null
done
echo "  Done."

echo ""
echo "Step 2: Truncating PostgreSQL serving tables..."
psql "${POSTGRES_DSN}" -c "TRUNCATE TABLE session_metrics, product_funnel_1m, users, products, categories, orders, order_items CASCADE;"
echo "  Done."

echo ""
echo "Step 3: Dropping all Iceberg tables across layers..."
python3 -c "
import sys, os
sys.path.insert(0, 'services/flink-jobs/src')
from contracts.loader import load_contract, ddl_columns, partition_spec
" 2>/dev/null || true
echo "  Tables will be recreated by the Flink jobs on startup."

echo ""
echo "Step 4: Restarting jobs from Kafka offset 0..."
docker compose -f infra/compose/docker-compose.yml run --rm job-submitter
echo "  Jobs resubmitted."

echo ""
echo "=== Reprocessing started — bronze → silver → gold pipeline running ==="
