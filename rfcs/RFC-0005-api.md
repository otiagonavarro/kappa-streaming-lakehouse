<!-- markdownlint-disable -->
# RFC-0005 - APIs e Contratos

- **Status:** Accepted
- **Autor:** Tiago Ribeiro Navarro de Andrade
- **Criado em:** 2026-07-19
- **Última atualização:** 2026-07-19
- **Versão:** 1.0

---

## REST

No REST API is authored by this bundle directly. Third-party REST surfaces exposed by the stack: Flink REST API (`:8081`, job control), Nessie REST API (catalog operations), Cube.js API (`:4000`, REST/SQL + Playground).

## gRPC

Not used in this bundle.

## Eventos

Two Kafka topics carry all domain events:

- **`raw-events`** — clickstream: `page_view`, `add_to_cart`, `purchase`.
- **`entity-updates`** — wide-schema, nullable-field CDC-style updates for `user`, `product`, `category`, `order`, `order_item` (see `adr/0010-wide-schema-cdc-topic.md` for why a single topic instead of one per entity type).

## Kafka

Broker: Redpanda (Kafka-API compatible). Topic contract for `raw-events` is defined via ODCS at `services/flink-jobs/contracts/raw_events.contract.yaml`, and is actually consumed at runtime by `services/flink-jobs/src/common.py` to build the Kafka source and Iceberg sink DDL for `raw_event_ingestion` — the contract is not just documentation, it is executable configuration.

## Pub/Sub

Not used; Kafka is the sole event bus.

## Payloads

Example `raw-events` payload shape (from the ODCS contract):

```json
{
  "event_id": "uuid",
  "event_type": "purchase",
  "user_id": "string",
  "session_id": "string",
  "product_id": "string | null",
  "event_timestamp": "2026-07-19T12:00:00.000000Z",
  "metadata": { "page_url": "...", "referrer": "..." }
}
```

Example `entity-updates` payload is a wide, mostly-null record — only the fields relevant to the entity type being updated are populated; consumers select fields based on an implicit entity-type discriminator in the payload.

## Versionamento

The ODCS raw-events contract and the Data Contract Specification medallion contracts (`contracts/{bronze,silver,gold}/`) are each versioned as individual files. There is currently no automated compatibility check (e.g. schema-registry-style backward-compatibility enforcement) between contract versions — a gap tracked in `rfcs/RFC-0010-roadmap.md`.
