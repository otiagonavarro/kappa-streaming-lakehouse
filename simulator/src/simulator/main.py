import json
import os
import signal
import sys
import time

import click # type: ignore
from kafka import KafkaProducer # type: ignore
try:
    from kafka.errors import NoBrokersAvailable # type: ignore
except ImportError:
    from kafka.errors import KafkaConnectionError as NoBrokersAvailable # type: ignore # kafka-python ≥3.0

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
@click.option("--entity-topic", default=lambda: os.environ.get("SIMULATOR_ENTITY_TOPIC", "entity-updates"), show_default=True)
@click.option("--rate", default=lambda: int(os.environ.get("SIMULATOR_RATE", "10")), type=int, help="Events per second")
@click.option("--count", default=0, type=int, help="Produce exactly N events then exit (0 = infinite)")
@click.option("--seed", default=None, type=int, help="RNG seed for reproducible output")
def cli(brokers: str, topic: str, entity_topic: str, rate: int, count: int, seed: int | None):
    """Publish synthetic e-commerce events to Kafka topics."""
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

    # Emit entity snapshots on startup (before the main event loop)
    click.echo(f"Seeding entity snapshots to {entity_topic}…")
    snapshots = generator.generate_entity_snapshots()
    for snap in snapshots:
        producer.send(entity_topic, value=snap)
    producer.flush()
    click.echo(f"  {len(snapshots)} entity snapshots sent ({len([s for s in snapshots if s['entity_type'] == 'user'])} users, "
               f"{len([s for s in snapshots if s['entity_type'] == 'product'])} products, "
               f"{len([s for s in snapshots if s['entity_type'] == 'category'])} categories)")

    click.echo(f"Producing to {brokers}/{topic} at {rate} eps (seed={seed}, count={'∞' if count == 0 else count})")

    while count == 0 or produced < count:
        start = time.monotonic()
        event = generator.generate()
        producer.send(topic, value=event)
        produced += 1

        # On purchase events, also emit order + order_item to entity-updates
        if event["event_type"] == "purchase":
            order = generator.generate_order(event["user_id"], event["product_id"])
            producer.send(entity_topic, value=order)
            item = generator.generate_order_item(
                order["order_id"], event["product_id"], event["metadata"]["items"]
            )
            producer.send(entity_topic, value=item)

        # Periodically emit entity updates (~every 100 events)
        if produced % 100 == 0:
            update = generator.generate_entity_update()
            if update is not None:
                producer.send(entity_topic, value=update)

        if produced % 100 == 0:
            click.echo(f"  {produced} events produced", err=True)

        elapsed = time.monotonic() - start
        sleep_for = interval - elapsed
        if sleep_for > 0:
            time.sleep(sleep_for)

    producer.flush()
    producer.close()
    click.echo(f"Done — {produced} events produced.")
