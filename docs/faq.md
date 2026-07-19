<!-- markdownlint-disable -->
# FAQ

**Q: Why does reprocessing replay the entire Kafka log instead of just the changed part?**
A: That's the core Kappa-architecture trade-off — see `rfcs/RFC-0001-problem.md` and `adr/0003-kappa-over-lambda.md`. There is no separate batch layer; full replay from offset 0 *is* the reprocessing mechanism. It's simpler and avoids batch/streaming divergence, at the cost of reprocessing cost scaling with total log size.

**Q: Are `entity_sync.py` and `order_ingestion.py` actually running?**
A: No. Both exist in `services/flink-jobs/src/`, but neither is included in `infra/job-submitter/submit_jobs.py`'s job list, so they never get submitted. This is a known, tracked gap — see `rfcs/RFC-0010-roadmap.md`.

**Q: Is this safe to deploy anywhere besides my laptop?**
A: No, not as-is. Every credential in the stack is a hardcoded default (see `rfcs/RFC-0006-security.md`), there's no TLS, no auth, no RBAC. This bundle is a local-development architecture demonstration, not a deployable system.

**Q: Why are there two different data-contract formats in this repo?**
A: `contracts/{bronze,silver,gold}/` use the Data Contract Specification 1.1.0 format; `services/flink-jobs/contracts/raw_events.contract.yaml` uses ODCS. This is a real, acknowledged inconsistency — see `rfcs/RFC-0004-data-model.md` and the "Refatorações" section of `rfcs/RFC-0010-roadmap.md`.

**Q: Can I point this at real Google Cloud Storage instead of MinIO?**
A: The code path exists (`STORAGE_BACKEND=gcs`), but it has never been verified against real GCS — see `adr/0006-minio-over-gcs-for-local-dev.md`. Treat it as unverified if you try it.

**Q: Why does `simulator`'s `session_id` not match the "real" session boundaries in the aggregated tables?**
A: The simulator's `session_id` is a synthetic per-event token (changes with 5% probability); the real session boundary is computed downstream by a 30-minute inactivity-gap rule in `silver_enrichment`/`session_aggregation`. See `rfcs/RFC-0003-domain-model.md`.

**Q: Where do I start if I want to understand the whole system before touching code?**
A: `README.md` for the pitch and quickstart, then `rfcs/RFC-0002-architecture.md` for the component map, then whichever RFC matches what you're changing (data model, security, scalability, etc.).
