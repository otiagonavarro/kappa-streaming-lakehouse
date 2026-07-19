---
name: pr-description
description: Draft (and optionally open) a pull request using this repo's .github/PULL_REQUEST_TEMPLATE.md. Use when the user asks to open a PR, write a PR description, or prep a branch for review.
license: MIT
metadata:
  author: portfolio
  version: "1.0"
---

Draft a pull request description for the current branch, filling in
`.github/PULL_REQUEST_TEMPLATE.md` from the actual diff and commit history —
never invent content the diff doesn't support.

**Steps**

1. **Gather branch state** (run in parallel):
   ```bash
   git status
   git branch --show-current
   git log main..HEAD --oneline
   git diff main...HEAD --stat
   ```
   If there's nothing ahead of `main`, tell the user and stop.

2. **Read the template**: `.github/PULL_REQUEST_TEMPLATE.md` at the repo root.
   If it doesn't exist, tell the user and stop rather than improvising a
   different format.

3. **Fill each section from evidence, not guesses**:
   - **Summary** — derive from the commit messages and diff, not just the
     latest commit. Lead with why, per this repo's commit-message style.
   - **Bundle / Scope** — check which top-level path the diff touches. Under
     a bundle directory (e.g. `kappa-streaming-lakehouse/`, or any directory
     matching `templates/bundle/`'s layout) → check that bundle's box and name
     it. Changes to `openspec/`, `RFC.md`, `Architecture-Bundles-Framework.md`,
     `templates/`, or root config → check "Portfolio root".
   - **Type of change** — match the Conventional Commits type(s) actually used
     in `git log main..HEAD`. If commits mix types, check all that apply and
     say so in Summary.
   - **Related RFCs / ADRs** — `git diff main...HEAD --name-only` for paths
     under `rfcs/` or `adr/` (or `openspec/changes/*/specs/`) and link them.
     If none touched but the diff is architecturally significant, flag this
     to the user instead of silently leaving it blank — a missing ADR for a
     significant decision is a real gap, not a template formality.
   - **Checklist** — check only what you can verify from the diff itself
     (e.g. "tests added/updated" only if test files changed; "Conventional
     Commits" only if `git log` confirms it). Leave unverifiable boxes
     unchecked rather than assuming.
   - **How to verify** — give the exact runnable command(s) a reviewer needs,
     e.g. `docker-compose -f infra/compose/docker-compose.yml up -d` for a
     bundle change, or `openspec validate <change> --strict` for an OpenSpec
     change.
   - **Risks / rollback** — one honest sentence; "None" is fine if genuinely
     low-risk.

4. **Show the filled template to the user** before doing anything else and
   ask whether to open the PR now or just leave the draft for them to use.

5. **If the user confirms opening the PR**, follow this repo's PR-creation
   safety rules (push only the current branch, never force-push, never
   fabricate a "Test plan" section that overrides this template) and run:
   ```bash
   git push -u origin <branch>
   gh pr create --title "<title>" --body-file <tmpfile-with-the-filled-template>
   ```
   Use a temp file (not an inline heredoc) so the template's own Markdown
   (checkboxes, HTML comments) survives verbatim. Report the PR URL back.

**Guardrails**

- Do not silently switch to the generic Summary/Test-plan PR format from
  default instructions — this repo's template is the source of truth.
- Do not check a checklist box you haven't verified from the diff or log.
- Do not push or open the PR without explicit confirmation from the user.
