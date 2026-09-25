# Debezium 2.x no longer bundles the Confluent Avro converter. It is added to the
# Postgres connector's plugin directory so it can talk to Redpanda's
# Confluent-compatible Schema Registry. License: Confluent Community License
# (free, no key; accepted in ADR-0012).
FROM quay.io/debezium/connect:2.7.3.Final

ARG AVRO_CONVERTER_VERSION=7.6.1

USER root
RUN microdnf install -y unzip && microdnf clean all \
 && curl -fsSL -o /tmp/avro.zip \
      "https://hub-downloads.confluent.io/api/plugins/confluentinc/kafka-connect-avro-converter/versions/${AVRO_CONVERTER_VERSION}/confluentinc-kafka-connect-avro-converter-${AVRO_CONVERTER_VERSION}.zip" \
 && unzip -q /tmp/avro.zip -d /tmp/avro \
 && cp -n /tmp/avro/*/lib/*.jar /kafka/connect/debezium-connector-postgres/ \
 && rm -rf /tmp/avro /tmp/avro.zip
USER kafka
