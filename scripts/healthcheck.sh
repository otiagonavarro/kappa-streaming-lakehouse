#!/usr/bin/env bash
# End-to-end pipeline health check.
# Exits 0 and prints "Pipeline healthy" on success.
set -euo pipefail

KAFKA_BROKERS=${KAFKA_BROKERS:-localhost:9092}
FLINK_API=${FLINK_API:-http://localhost:8081}
POSTGRES_DSN=${POSTGRES_DSN:-postgresql://kappa:kappa@localhost:5432/kappa}
NESSIE_URI=${NESSIE_URI:-http://localhost:19120/api/v1}

PASS=0
FAIL=0

check() {
    local label="$1"
    local cmd="$2"
    if eval "$cmd" &>/dev/null; then
        echo "  ✓ ${label}"
        PASS=$((PASS + 1))
    else
        echo "  ✗ ${label}"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== Pipeline Health Check ==="
echo ""

# 1. Kafka topic exists
check "Kafka topic 'raw-events' exists" \
    "docker compose -f infra/docker-compose.yml exec -T broker rpk topic list | grep -q raw-events"

# 2. Flink JobManager reachable
check "Flink JobManager reachable" \
    "curl -sf ${FLINK_API}/overview"

# 3. Streaming jobs running — query Flink REST API for at least one RUNNING job
check "Flink streaming jobs running" \
    "curl -sf ${FLINK_API}/jobs | python3 -c \"import sys,json; d=json.load(sys.stdin); sys.exit(0 if any(j['status']=='RUNNING' for j in d.get('jobs',[])) else 1)\""

# 4. Nessie catalog reachable
check "Nessie REST catalog reachable" \
    "curl -sf ${NESSIE_URI}/config"

# 5. PostgreSQL session_metrics has data
check "PostgreSQL session_metrics is non-empty" \
    "python3 -c \"import psycopg2; c=psycopg2.connect('${POSTGRES_DSN}'); cur=c.cursor(); cur.execute('SELECT COUNT(*) FROM session_metrics'); n=cur.fetchone()[0]; sys.exit(0 if n > 0 else 1)\" 2>/dev/null || psql '${POSTGRES_DSN}' -tAc 'SELECT COUNT(*) FROM session_metrics' | grep -qv '^0$'"

# 6. PostgreSQL product_funnel_1m has data
check "PostgreSQL product_funnel_1m is non-empty" \
    "psql '${POSTGRES_DSN}' -tAc 'SELECT COUNT(*) FROM product_funnel_1m' | grep -qv '^0$'"

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"

if [ "${FAIL}" -eq 0 ]; then
    echo ""
    echo "Pipeline healthy"
    exit 0
else
    echo ""
    echo "Pipeline has issues — check logs with: make logs"
    exit 1
fi
