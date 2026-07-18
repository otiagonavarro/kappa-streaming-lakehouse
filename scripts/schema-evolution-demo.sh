#!/usr/bin/env bash
# Schema evolution demo: add campaign_id column to kappa.raw_events without rewriting files.
set -euo pipefail

NESSIE_URI=${NESSIE_URI:-http://localhost:19120/api/v1}
POSTGRES_DSN=${POSTGRES_DSN:-postgresql://kappa:kappa@localhost:5432/kappa}

echo "=== Kappa Architecture — Schema Evolution Demo ==="

echo ""
echo "Step 1: Current schema of kappa.raw_events"
python3 -c "
from pyflink.table import EnvironmentSettings, TableEnvironment
import os
env = TableEnvironment.create(EnvironmentSettings.in_batch_mode())
env.execute_sql(\"USE CATALOG nessie_catalog\")
result = env.execute_sql(\"DESCRIBE kappa.raw_events\")
result.print()
"

echo ""
echo "Step 2: Count rows before schema change"
PRE_COUNT=$(python3 scripts/count-iceberg-rows.py raw_events)
echo "Row count before: ${PRE_COUNT}"

echo ""
echo "Step 3: Adding campaign_id column via Iceberg ALTER TABLE..."
python3 -c "
from pyflink.table import EnvironmentSettings, TableEnvironment
env = TableEnvironment.create(EnvironmentSettings.in_batch_mode())
env.execute_sql(\"USE CATALOG nessie_catalog\")
env.execute_sql(\"ALTER TABLE kappa.raw_events ADD COLUMN campaign_id STRING\")
print('Column added successfully.')
"

echo ""
echo "Step 4: Verify existing rows return NULL for campaign_id (no file rewrite)"
python3 -c "
from pyflink.table import EnvironmentSettings, TableEnvironment
env = TableEnvironment.create(EnvironmentSettings.in_batch_mode())
env.execute_sql(\"USE CATALOG nessie_catalog\")
result = env.execute_sql(\"SELECT campaign_id FROM kappa.raw_events LIMIT 5\")
result.print()
print('All values above should be NULL — no data files were rewritten.')
"

echo ""
echo "Step 5: New events will have campaign_id populated by the simulator"
echo "  Set CAMPAIGN_ID env var on the simulator to tag events."

echo ""
echo "=== Demo complete — schema evolved with zero downtime and zero file rewrite ==="
