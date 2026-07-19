<!-- markdownlint-disable -->
# ADR-0010 - Single wide-schema entity-updates topic over per-entity topics

- **Status:** Accepted
- **Data:** 2026-07-19 (retroactive — decision predates this ADR; see commit `2e715b0`)

---

## Contexto

Modeling a realistic e-commerce domain requires propagating updates for five entity types (`user`, `product`, `category`, `order`, `order_item`) as CDC-style events, alongside the existing clickstream topic.

## Problema

Should each entity type get its own Kafka topic, or should all five share a single topic with a wide, mostly-null schema?

## Alternativas

1. **Per-entity-type topics** (`user-updates`, `product-updates`, `category-updates`, `order-updates`, `order-item-updates`) — stronger per-entity typing, no wasted null fields per message. Cons: five separate consumers/deserializers/schemas to maintain in every consuming job, and five topics to keep partition/retention-configured consistently.
2. **Single wide-schema `entity-updates` topic (chosen)** — one topic, one consumer/deserializer path across all entity types, at the cost of a sparse/nullable schema where most fields on any given message are null (only the fields relevant to that message's entity type are populated).

## Decisão

Single `entity-updates` topic with a wide, nullable schema, distinguished by an implicit entity-type discriminator in the payload. Documented rationale (from `docs/flink-jobs.md`, carried into this ADR): avoids the operational overhead of maintaining five separate consumers/deserializers in every job that needs entity data.

## Consequências

- Simpler consumer code path — one topic to subscribe to, one deserialization path, for any job that needs entity updates.
- Weaker per-entity typing than dedicated topics would provide — consumers must branch on the implicit entity-type discriminator and know which fields are meaningful for each type.
- Schema evolution of any single entity type touches the shared wide schema, which is more coupling than per-entity topics would have, but was judged an acceptable trade for this bundle's scope.
