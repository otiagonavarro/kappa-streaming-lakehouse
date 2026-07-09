.PHONY: up down check reprocess logs sim-start sim-stop

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
