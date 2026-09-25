<!-- markdownlint-disable -->
# ADR-0014 - Source-aligned silver with `_changes` and current-state tables

- **Status:** Accepted (amends ADR-0009)
- **Data:** 2026-09-25
- **Feature:** [`docs/features/2026-09-25-oltp-cdc-lakehouse/`](../docs/features/2026-09-25-oltp-cdc-lakehouse/spec.md)

---

## Contexto

Business logic has leaked into silver: sessionization (`silver.user_sessions`, a 30-minute business rule) lives there. There is no stated boundary for what silver may do. Separately, with chained layers (ADR-0013), gold must stream from silver. The Flink Iceberg source only consumes `append` snapshots, so a silver table maintained by upserts (equality deletes) cannot be streamed.

## Problema

What belongs in silver, and how can silver expose both a current-state view and a streamable changelog?

## Alternativas

Boundary: silver is **source-aligned** (chosen): one silver table per source entity, same grain and meaning as bronze. Technical treatment only: typing, naming, dedup, applying the changelog, quarantine of malformed events. Joins across entities, derived metrics, sessionization and business classifications go to gold.

Streaming over upserts:

1. **Two outputs per entity (chosen)** — `silver.<table>_changes` (append-only, cleaned, deduplicated, streamed by gold) and `silver.<table>` (upsert current state, for ad hoc queries only).
2. **Append-only silver only** — current state becomes each consumer's `ROW_NUMBER()` problem, and the rule is scattered.
3. **Apache Paimon for silver** — native changelog streaming reads, but a second table format contradicts ADR-0004.
4. **Batch gold over upserted silver** — abandons end-to-end streaming.

## Decisão

Silver is source-aligned. Each CDC entity gets a `_changes` table (append-only, deduplicated on `(pk, _source_lsn)`, snapshot `op=r` treated as an upsert) and a current-state table (Top-1 by `_source_lsn` per primary key, with `_is_deleted`, `_source_lsn`, `_updated_at`). The clickstream gets a validated table plus a quarantine table with `_reject_reason`. Gold streams only from `_changes` and validated clickstream.

## Consequências

- A clear, reviewable rule for silver. Sessionization moves to `gold.sessions`.
- Silver holds 2 tables per CDC entity (18) plus 2 clickstream tables. Each has one clear role.
- The Iceberg streaming source does not guarantee per-key ordering across splits. Every silver and gold computation is therefore order-independent (dedup/Top-1 by LSN, `MAX` per stage, self-join for SCD2 `valid_to`), never relying on arrival order.
- Current-state tables use Iceberg v2 equality deletes. Whether Doris 4.1.3 reads them correctly is validated by a spike before silver is built, with a fallback of a Top-1 view over `_changes`.
