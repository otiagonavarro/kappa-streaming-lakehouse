<!-- markdownlint-disable -->
# ADR-0015 - PII hashed at the bronze edge

- **Status:** Accepted
- **Data:** 2026-09-25
- **Feature:** [`docs/features/2026-09-25-oltp-cdc-lakehouse/`](../docs/features/2026-09-25-oltp-cdc-lakehouse/spec.md)

---

## Contexto

Customers and addresses carry PII (email, phone, document, street address). Bronze is an append-only changelog (ADR-0013), so PII stored there in clear text would persist forever: in every `before`/`after`, in older Iceberg snapshots, and under time travel. That conflicts with LGPD's right to erasure.

## Problema

Where should PII be protected so that an erasure request in the OLTP does not require purging the lakehouse?

## Alternativas

1. **Hash at the edge, in bronze (chosen)** — the `bronze_cdc` job replaces PII columns with HMAC-SHA256 (`PII_HMAC_KEY`) before writing. Clear-text PII never enters the lakehouse.
2. **Clear text in bronze + a "forget" purge job** — rewrite bronze (`DELETE WHERE customer_id = ?`), then expire snapshots and remove orphans. Faithful to "raw bronze", but complex, easy to forget, and it breaks changelog immutability.
3. **Crypto-shredding** — encrypt PII with a per-customer key and delete the key on erasure. Elegant, but it needs a KMS or a key table; kept on the roadmap.

## Decisão

HMAC-SHA256 at the bronze edge for `customers.email`, `customers.phone`, `customers.document`, `addresses.street`, `addresses.number` and `addresses.zip_code`. City and state stay in clear text as analytical dimensions. In the OLTP, `forget_customer` anonymizes (nulls PII) and soft-deletes the customer.

## Consequências

- Bronze is no longer 100 % raw: it keeps the envelope structure, `op` and LSN, but not the sensitive values. Silver no longer owns PII masking.
- Hashes are deterministic, so hashed columns remain joinable and countable (e.g. distinct emails).
- Rotating `PII_HMAC_KEY` breaks continuity and joins on hashed columns; rotation is out of scope and documented.
- Flink SQL has no built-in HMAC, so it is a PyFlink Python scalar UDF. Its throughput is measured in the bronze phase, with a Java UDF as fallback.
- Clear-text PII still exists transiently in Redpanda (7-day retention) and in the OLTP, which are outside the lakehouse's erasure scope.
