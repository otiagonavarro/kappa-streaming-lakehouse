<!-- markdownlint-disable -->
# ADR-0009 - Bronze/Silver/Gold medallion architecture with per-layer data contracts

- **Status:** Accepted
- **Data:** 2026-07-19 (retroactive — decision predates this ADR; see commit `16401d9`)

---

## Contexto

Raw clickstream events need validation, enrichment, and aggregation before they're useful for dashboards and analysis. The original pipeline wrote a single flat table; commit `16401d9` migrated it to a layered Bronze/Silver/Gold model with Data Contract Specification 1.1.0 contracts per table.

## Problema

Should the lakehouse use a single flat table for all processing stages, or a layered medallion model with explicit contracts per layer?

## Alternativas

1. **Flat single-layer model** — simpler initially, fewer tables. Cons: no explicit validation/enrichment boundary; consumers can't tell whether a given table's data has been validated, deduplicated, or is genuinely raw; no clear per-layer ownership.
2. **Bronze/Silver/Gold medallion with per-layer contracts (chosen)** — Bronze holds raw events as received; Silver holds validated/enriched events (malformed/future/stale events dropped, page_url/referrer extracted); Gold holds pre-aggregated, consumption-ready tables (`session_metrics`, `product_funnel_1m`, `user_360`). Each layer/table has its own Data Contract Specification contract under `contracts/{bronze,silver,gold}/`.

## Decisão

Bronze/Silver/Gold medallion architecture, each table backed by its own Data Contract Specification 1.1.0 contract file.

## Consequências

- Clear validation boundary: anything in Silver or later is guaranteed to have passed the validation rules in `rfcs/RFC-0003-domain-model.md` ("Regras de Negócio").
- More moving pieces than a flat model — more tables, more contracts, more Flink jobs (`raw_event_ingestion` → `silver_enrichment` → `session_aggregation`/`product_funnel` → `user_360`) to keep consistent.
- Two contract standards now coexist in the bundle (Data Contract Specification for medallion tables, ODCS for the raw-events Kafka/Iceberg DDL — see ADR-0008) — a known inconsistency, tracked as a refactoring item in `rfcs/RFC-0010-roadmap.md` rather than silently normalized away.
