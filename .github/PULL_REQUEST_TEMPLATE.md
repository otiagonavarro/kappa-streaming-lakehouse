<!-- markdownlint-disable -->
## Summary

<!-- 1-3 bullets: what changed and why. Lead with the "why". -->

-

## Bundle / Scope

<!-- Which bundle(s) does this touch, or is this a portfolio-root change? -->

- [ ] Portfolio root (governance, conventions, templates)
- [ ] Bundle: `<bundle-name>`

## Type of change

<!-- Matches the Conventional Commits type used in this PR's commits. -->

- [ ] `feat` — new capability or bundle content
- [ ] `fix` — bug or defect fix
- [ ] `docs` — documentation only (RFCs, ADRs, README, etc.)
- [ ] `refactor` — no behavior change
- [ ] `chore` / `ci` — tooling, CI, deps

## Related RFCs / ADRs

<!-- Link the RFC(s) this implements and any ADR(s) this adds or updates.
     New architecturally- or business-significant decisions need a new ADR — see
     specs/bundle-structure-standard/spec.md#adr-usage. -->

-

## Checklist

<!-- Per specs/portfolio-conventions/spec.md and specs/bundle-structure-standard/spec.md -->

- [ ] Commit messages follow Conventional Commits
- [ ] Branch follows the naming scheme (`feature/*`, `fix/*`, `docs/*` off `develop`)
- [ ] New significant decisions are recorded as ADRs (context, problem, alternatives, decision, consequences)
- [ ] Affected RFCs / `docs/tradeoffs.md` updated if this changes architecture or trade-offs
- [ ] Diagrams updated (Mermaid, versioned alongside code) if this changes a flow or component
- [ ] Tests added/updated and passing
- [ ] `README.md` still answers what/problem/how-to-run/architecture/tech/structure/roadmap in under 5 minutes
- [ ] No bundle-local `LICENSE` drift (bundle copy matches portfolio root `LICENSE`)

## How to verify

<!-- Exact commands a reviewer runs to see this working, e.g.:
     docker-compose -f infra/compose/docker-compose.yml up -d
     then... -->

```bash

```

## Risks / rollback

<!-- What could break, and how to revert if it does. "None" is a valid answer. -->
