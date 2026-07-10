#!/usr/bin/env bash
# Full reprocessing: stop Flink jobs, truncate sinks, restart from Kafka offset 0.
# Demonstrates the core Kappa architecture property: all state is re-derivable from the event log.
set -euo pipefail

FLINK_API=${FLINK_API:-http://localhost:8081}
POSTGRES_DSN=${POSTGRES_DSN:-postgresql://kappa:kappa@localhost:5432/kappa}

echo "=== Kappa Reprocessing ==="
echo ""

# 1. Cancel all running Flink jobs
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

# 2. Truncate PostgreSQL serving tables
echo ""
echo "Step 2: Truncating PostgreSQL serving tables..."
psql "${POSTGRES_DSN}" -c "TRUNCATE TABLE session_metrics, product_funnel_1m, users, products, categories, orders, order_items CASCADE;"
echo "  Done."

# 3. Drop and recreate Iceberg tables (via Nessie branch reset would be ideal in production)
echo ""
echo "Step 3: Truncating Iceberg tables via Nessie..."
echo "  (In production: create a new Nessie branch, reprocess, then merge)"
python3 scripts/init-iceberg-tables.py --drop-if-exists 2>/dev/null || true
echo "  Done."

# 4. Restart jobs with --from-beginning
echo ""
echo "Step 4: Restarting jobs from Kafka offset 0..."
docker compose -f infra/docker-compose.yml run --rm job-submitter
echo "  Jobs resubmitted."

echo ""
echo "=== Reprocessing started — monitor at http://localhost:8081 ==="
