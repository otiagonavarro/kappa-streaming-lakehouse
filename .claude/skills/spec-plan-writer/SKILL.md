---
name: spec-plan-writer
description: After an intent.md is approved, generate spec.md (requirements & design — Stage 2) and then plan.md (implementation plan — Stage 3) in the same feature folder, per Anthropic's AI-native SDLC playbook. Trigger when the user says the intent.md is approved and wants to move to design/spec, or asks to generate spec.md or plan.md for a feature. Never writes or edits implementation code — "nothing is implemented without an accepted plan.md".
---

This skill produces the two remaining AI-native SDLC artifacts for a feature already covered by an approved `intent.md`: `spec.md` (Design stage) and then `plan.md` (Build-planning stage), both written to the same `docs/features/<date>-<feature>/` folder.

Do NOT implement anything in this skill — no code edits. Its output is documents only.

<!-- markdownlint-disable -->
## Process

### Stage A — spec.md (Design)

1. **Locate and validate the feature folder.** Ask the user which feature, or infer it from the most recently written `docs/features/*/intent.md`. Read `intent.md` fully. If it doesn't exist, or its `Status` is not `Approved`, stop and tell the user to run `intent-writer` (or get it approved) first — do not draft a spec against an unapproved intent.

2. **Ground the design in the actual codebase**, not just the intent text:
   - Look for existing patterns to follow (e.g. `cloud-run-projects` / `data-ingestion-projects` conventions if this is a new service/function).
   - For API/service-surface changes, check `docs/service-graph.mmd` for downstream consumers.
   - Use GitNexus `query()`/`context()` to find related execution flows and existing symbols this will touch or extend, per this project's usual exploration approach.

3. **Draft `spec.md`** from the template below. Compress requirements + design into one document — don't pad it with restated intent content.

4. **Show the draft, iterate until the user explicitly approves it.** Write `spec.md` into the feature folder with `Status: Approved`, and update `intent.md`'s `Status` to `Approved` if it wasn't already.

### Stage B — plan.md (Build planning)

Only start this after spec.md is approved.

5. **Interview like Claude Code's plan mode**: propose an implementation strategy — don't just dump a finished plan. Iterate on file list, work order, and risks with the engineer until they accept it.

6. **Before finalizing any part of the plan that touches an existing function, class, or method in this repo, run `impact({target, direction: "upstream"})`** (per this project's root `CLAUDE.md`) and fold any HIGH/CRITICAL findings into the plan's Risks section — surface them to the user explicitly, don't silently soften them.

7. **Draft `plan.md`** from the template below.

8. **Show the draft, get explicit approval.** Write `plan.md` into the feature folder with `Status: Approved`.

9. **Remind the user**: implementation should not start without this `plan.md` being accepted, and after implementing, `detect_changes()` should be run to confirm the diff matches this plan (per this project's `CLAUDE.md`) before committing.

<spec-template>

# Spec: \<Feature Name\>

**Date:** \<YYYY-MM-DD\> · **Status:** Draft | Approved · **Source:** intent.md

## Functional Requirements

## Design / Architecture Decisions

Data model, API contracts, interfaces, modules touched or created.

## Edge Cases & Error Handling

## Security / Compliance Considerations

## Testing Approach

High-level only — the how-we'll-verify-this, not the test plan itself (that's plan.md).

## Open Questions Resolved

Which of intent.md's open questions this closes, and how. List any still open.

</spec-template>

<plan-template>

# Plan: \<Feature Name\>

**Date:** \<YYYY-MM-DD\> · **Status:** Draft | Approved · **Source:** spec.md

## Files to Change

## Work Order

Sequenced steps.

## Tests Required

## Risks & Mitigations

Include any HIGH/CRITICAL findings from `impact()` runs, with mitigation or explicit acceptance.

## Rollback Plan

</plan-template>
