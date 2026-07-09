import json
import os
import signal
import sys
import time

import click
from kafka import KafkaProducer
try:
    from kafka.errors import NoBrokersAvailable
except ImportError:
    from kafka.errors import KafkaConnectionError as NoBrokersAvailable  # kafka-python ≥3.0

from .events import EventGenerator


def _make_producer(brokers: str, retries: int = 10) -> KafkaProducer:
    last_exc: Exception = NoBrokersAvailable()
    for attempt in range(1, retries + 1):
        try:
            return KafkaProducer(
                bootstrap_servers=brokers.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
            )
        except NoBrokersAvailable as exc:
            last_exc = exc
            if attempt < retries:
                click.echo(f"Broker not ready (attempt {attempt}/{retries}), retrying in 3s…", err=True)
                time.sleep(3)
    raise last_exc


@click.command()
@click.option("--brokers", default=lambda: os.environ.get("KAFKA_BROKERS", "localhost:9092"), show_default=True)
@click.option("--topic", default=lambda: os.environ.get("SIMULATOR_TOPIC", "raw-events"), show_default=True)
@click.option("--rate", default=lambda: int(os.environ.get("SIMULATOR_RATE", "10")), type=int, help="Events per second")
@click.option("--count", default=0, type=int, help="Produce exactly N events then exit (0 = infinite)")
@click.option("--seed", default=None, type=int, help="RNG seed for reproducible output")
def cli(brokers: str, topic: str, rate: int, count: int, seed: int | None):
    """Publish synthetic e-commerce events to a Kafka topic."""
    generator = EventGenerator(seed=seed)
    producer = _make_producer(brokers)

    produced = 0
    interval = 1.0 / rate if rate > 0 else 0.0

    def _shutdown(sig, frame):
        click.echo(f"\nShutting down — produced {produced} events.", err=True)
        producer.flush()
        producer.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    click.echo(f"Producing to {brokers}/{topic} at {rate} eps (seed={seed}, count={'∞' if count == 0 else count})")

    while count == 0 or produced < count:
        start = time.monotonic()
        event = generator.generate()
        producer.send(topic, value=event)
        produced += 1

        if produced % 100 == 0:
            click.echo(f"  {produced} events produced", err=True)

        elapsed = time.monotonic() - start
        sleep_for = interval - elapsed
        if sleep_for > 0:
            time.sleep(sleep_for)

    producer.flush()
    producer.close()
    click.echo(f"Done — {produced} events produced.")
