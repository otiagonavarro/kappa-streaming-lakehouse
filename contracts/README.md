# Data contracts

One ODCS v3 contract per lakehouse table, laid out as `contracts/{bronze,silver,gold}/<table>.odcs.yaml` (ADR-0008, amended 2026-09-25).

The contracts arrive with their layers: bronze in phase 2, silver in phase 3, and gold in phase 4 of the [OLTP + CDC redesign plan](../docs/features/2026-09-25-oltp-cdc-lakehouse/plan.md).
