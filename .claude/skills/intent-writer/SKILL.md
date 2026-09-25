---
name: intent-writer
description: Interview the user to draft an intent.md — the "what's wanted, why, and under which constraints" proto-spec from Anthropic's AI-native SDLC playbook (Stage 1: Plan). Trigger when the user wants to capture a new feature/change idea, kick off a new initiative, says the intent.md needs to be written, or asks to be "grilled" about a feature before scoping starts. Writes docs/features/<date>-<feature>/intent.md for the product owner to review and approve — the file that gates the spec-plan-writer skill.
---

<!-- markdownlint-disable -->
This skill produces `intent.md`, the first artifact in the AI-native SDLC (intent → spec → plan). It replaces lengthy refinement/committee cycles with a direct interview: brainstorm with the user, write the proto-spec, get it corrected and approved before it's committed.

Do NOT design a solution here and do NOT write spec.md or plan.md — that's the companion `spec-plan-writer` skill, and it only runs after this file is approved.

## Process

1. **Locate the feature folder.** Get a short feature name from the user (or derive one from what they've described) and slugify it. The folder is `docs/features/<YYYY-MM-DD>-<slug>/` using today's date. If `docs/features/*-<slug>/intent.md` already exists, treat this as a revision: read the existing file first and interview only about what's changing.

2. **Grill the user.** Ask direct, pointed questions — one topic at a time, not a giant form — until each of these is concrete enough to act on:
   - **Problem statement**: what's broken or missing today, for whom, observed how.
   - **Why now**: the actual driver (incident, deadline, request, cost, compliance) — not just "would be nice."
   - **Proposed outcome**: what "done" looks like; measurable if at all possible.
   - **Affected users/systems**: who and what touches this. If it's an API/service change, cross-check `docs/service-graph.mmd` for downstream consumers and name them.
   - **Constraints**: technical, deadline, budget, compliance, backward-compatibility.
   - **Out of scope**: what this explicitly does not cover.
   - **Open questions**: real unknowns, not filler.

   If an answer is vague ("somehow", "not sure", "TBD"), push back once with a sharper follow-up. If it's still vague after that, stop pushing and record it as an Open Question instead of stalling the interview.

3. **Draft `intent.md`** from the template below using only what the user actually said — don't invent constraints or scope they didn't mention.

4. **Show the draft** to the user and get explicit approval or corrections. Iterate — this is the product owner's document, not yours; their edits win.

5. **On approval**: create the folder if needed, write `intent.md` with `Status: Approved`, and tell the user the path plus that `spec-plan-writer` picks up from here.

<intent-template>

# Intent: \<Feature Name\>

**Date:** \<YYYY-MM-DD\> · **Status:** Draft | Approved · **Owner:** \<user\>

## Problem Statement

What's wrong or missing today, from the affected users'/systems' perspective.

## Why Now

The concrete driver — incident, deadline, request, cost, compliance, opportunity.

## Proposed Outcome

What "done" looks like. Measurable where possible.

## Affected Users / Systems

Who and what this touches — teams, services, downstream consumers (check `docs/service-graph.mmd` for API/service changes).

## Constraints

Technical, deadline, budget, compliance, backward-compatibility.

## Out of Scope

What this explicitly does not cover.

## Open Questions

Real unknowns still unresolved, to be closed out before or during spec.md.

</intent-template>
