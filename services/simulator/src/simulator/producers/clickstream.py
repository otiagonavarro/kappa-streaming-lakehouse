"""Avro clickstream producer. The schema is registered in the Redpanda Schema Registry
(TopicNameStrategy) on first send; events are keyed by session_id so a session's
events stay ordered within one partition."""
from importlib import resources

from confluent_kafka import KafkaError, Message, SerializingProducer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import StringSerializer


def clickstream_schema() -> str:
    return resources.files("simulator").joinpath("schemas/clickstream_event.avsc").read_text()


class ClickstreamProducer:
    def __init__(self, brokers: str, registry_url: str, topic: str):
        self._topic = topic
        self.failed = 0
        self._producer = SerializingProducer(
            {
                "bootstrap.servers": brokers,
                "acks": "all",
                "enable.idempotence": True,
                "linger.ms": 50,
                "key.serializer": StringSerializer("utf_8"),
                "value.serializer": AvroSerializer(SchemaRegistryClient({"url": registry_url}), clickstream_schema()),
            }
        )

    def send(self, event: dict) -> None:
        self._producer.produce(self._topic, key=event["session_id"], value=event, on_delivery=self._on_delivery)
        self._producer.poll(0)

    def flush(self, timeout: float = 10.0) -> int:
        """Wait for in-flight events; returns how many are still undelivered."""
        return self._producer.flush(timeout)

    def _on_delivery(self, err: KafkaError | None, _msg: Message) -> None:
        if err is not None:
            self.failed += 1
