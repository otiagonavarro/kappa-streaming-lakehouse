.PHONY: up down check reprocess logs sim-start sim-stop submit-jobs jobs-status

up:
	cp -n .env.example .env 2>/dev/null || true
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down -v

check:
	@bash scripts/healthcheck.sh

reprocess:
	@bash scripts/reprocess.sh

logs:
	docker compose -f infra/docker-compose.yml logs -f

sim-start:
	docker compose -f infra/docker-compose.yml start simulator

sim-stop:
	docker compose -f infra/docker-compose.yml stop simulator

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
	@echo "  demo-time-travel - Run the time travel demo"
	@echo "  demo-schema-evolution - Run the schema evolution demo"
	@echo "  help - Show this help message"
