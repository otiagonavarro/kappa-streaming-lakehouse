.PHONY: up down check reprocess logs sim-start sim-stop submit-jobs jobs-status connect-status test-simulator

up:
	cp -n .env.example .env 2>/dev/null || true
	docker compose -f infra/compose/docker-compose.yml up -d

down:
	docker compose -f infra/compose/docker-compose.yml down -v

check:
	@bash scripts/healthcheck.sh

reprocess:
	@bash scripts/reprocess.sh

logs:
	docker compose -f infra/compose/docker-compose.yml logs -f

sim-start:
	docker compose -f infra/compose/docker-compose.yml start simulator

sim-stop:
	docker compose -f infra/compose/docker-compose.yml stop simulator

connect-status:
	@curl -s http://localhost:8083/connectors/shop-postgres-cdc/status | python3 -m json.tool

test-simulator:
	cd services/simulator && uv run --extra dev pytest -q ../../tests/simulator

demo-time-travel:
	@bash scripts/time-travel-demo.sh

demo-schema-evolution:
	@bash scripts/schema-evolution-demo.sh

help:
	@echo "Usage: make <target>"
	@echo "Targets:"
	@echo "  up - Start the infrastructure"
	@echo "  down - Stop the infrastructure"
	@echo "  check - Check the health of the infrastructure"
	@echo "  reprocess - Reprocess the data"
	@echo "  logs - View the logs of the infrastructure"
	@echo "  sim-start - Start the simulator"
	@echo "  sim-stop - Stop the simulator"
	@echo "  connect-status - Show the Debezium connector status"
	@echo "  test-simulator - Run simulator tests (needs Docker for Postgres)"
	@echo "  demo-time-travel - Run the time travel demo"
	@echo "  demo-schema-evolution - Run the schema evolution demo"
	@echo "  help - Show this help message"
