<!-- markdownlint-disable -->
# ADR-0006 - MinIO over GCS for local development

- **Status:** Accepted
- **Data:** 2026-07-19 (retroactive — decision predates this ADR; originally narrated in `docs/trade-offs.md`)

---

## Contexto

The Iceberg lakehouse needs S3-compatible object storage. The bundle needs to run fully locally (per `bundle-structure-standard`'s "runnable in under five minutes" requirement) without requiring cloud credentials or incurring cost.

## Problema

Should the default object storage backend be a real cloud provider (GCS) or a local S3-compatible emulator (MinIO)?

## Alternativas

1. **GCS directly** — matches a real production target, no local/cloud behavioral drift. Cons: requires cloud credentials and a GCP project to run the bundle at all, incurs cost, and breaks the "runnable locally in under five minutes" goal for anyone without existing GCP access.
2. **MinIO (chosen), with GCS as a documented switch** — zero cost, zero external dependency, full S3 API compatibility, and the bundle stays runnable via `docker compose up` alone. `STORAGE_BACKEND=gcs` is implemented as a code-level switch for anyone who wants to point the bundle at real GCS.

## Decisão

MinIO by default; `STORAGE_BACKEND=gcs` supported as an alternative, not the default.

| Criterion | MinIO (local dev) | GCS |
| --- | --- | --- |
| Cost | Free (local Docker) | Pay-per-GB stored + egress |
| Setup | `docker compose up` | GCP project, bucket, IAM, service-account key |
| S3 API compatibility | Full — Iceberg sees it as S3 | Requires `gcs-connector-hadoop` |
| Consistency | Strong (single node) | Strong (Google's multi-region) |
| Scale | Single-node toy | Unlimited, globally replicated |
| When to use GCS instead | Never for local dev | Production; `STORAGE_BACKEND=gcs` activates it — no code changes, only env vars |

## Consequências

- Anyone can clone and run the full bundle locally with zero cloud setup — directly supports `bundle-structure-standard`'s five-minute runnability requirement.
- The GCS code path is real but **untested** — no evidence it has ever been exercised against actual GCS (verified during this retrofit; tracked in `rfcs/RFC-0010-roadmap.md`). Anyone relying on `STORAGE_BACKEND=gcs` today should treat it as unverified, not production-ready.
