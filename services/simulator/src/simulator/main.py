"""Shop application simulator: one process that plays the storefront (clickstream +
checkout), the back office (catalog/customer churn) and the order workers
(payment, shipping, delivery, refunds) against the OLTP database."""
import os
import random
import signal
import time

import click
import psycopg

from .config import SimConfig
from .producers.clickstream import ClickstreamProducer
from .seed import seed_if_empty
from .traffic.backoffice import Backoffice
from .traffic.sessions import TrafficGenerator
from .workers.progress import advance_orders

TICK_SECONDS = 1.0


def _connect(dsn: str, retries: int = 30) -> psycopg.Connection:
    for attempt in range(1, retries + 1):
        try:
            return psycopg.connect(dsn, autocommit=True)
        except psycopg.OperationalError:
            if attempt == retries:
                raise
            click.echo(f"Postgres not ready (attempt {attempt}/{retries}), retrying in 2s…", err=True)
            time.sleep(2)
    raise AssertionError("unreachable")


@click.command()
@click.option("--postgres-dsn", default=lambda: os.environ.get("POSTGRES_DSN", "postgresql://kappa:kappa@localhost:5432/kappa"))
@click.option("--brokers", default=lambda: os.environ.get("KAFKA_BROKERS", "localhost:9092"), show_default=True)
@click.option(
    "--schema-registry",
    default=lambda: os.environ.get("SCHEMA_REGISTRY_URL", "http://localhost:8081"),
    show_default=True,
)
@click.option(
    "--topic", default=lambda: os.environ.get("CLICKSTREAM_TOPIC", "clickstream.events"), show_default=True
)
@click.option("--customers", default=200, show_default=True, help="Customers created by the first-boot seed")
@click.option("--seed", default=None, type=int, help="RNG seed for reproducible behaviour")
@click.option("--ticks", default=0, type=int, help="Run N one-second ticks then exit (0 = forever)")
def cli(postgres_dsn, brokers, schema_registry, topic, customers, seed, ticks):
    """Run the shop application against Postgres and publish clickstream to Redpanda."""
    cfg = SimConfig.from_env()
    rng = random.Random(seed)
    conn = _connect(postgres_dsn)
    if seed_if_empty(conn, rng, customers=customers):
        click.echo(f"Seeded catalog and {customers} customers.")

    producer = ClickstreamProducer(brokers, schema_registry, topic)
    traffic = TrafficGenerator(conn, cfg, rng, producer.send)
    office = Backoffice(conn, cfg, rng)

    running = True

    def _stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    click.echo(f"Running: 1 simulated day = {cfg.seconds_per_day:g}s, {cfg.sessions_per_second:g} sessions/s → {topic}")
    tick = 0
    while running and (ticks == 0 or tick < ticks):
        started = time.monotonic()
        traffic.tick(TICK_SECONDS)
        office.tick()
        progressed = advance_orders(conn, cfg, rng)
        tick += 1
        if tick % 30 == 0:
            click.echo(f"tick {tick}: traffic={traffic.stats} orders={dict(progressed)} send_failures={producer.failed}")
        time.sleep(max(0.0, TICK_SECONDS - (time.monotonic() - started)))

    producer.flush()
    conn.close()
    click.echo(f"Stopped after {tick} ticks: {traffic.stats}")
