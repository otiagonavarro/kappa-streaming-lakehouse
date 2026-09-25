---
name: to-spec
description: Turn the current conversation into a spec and write it to .scratch/<feature-slug>/spec.md — no interview, just synthesis of what you've already discussed.
disable-model-invocation: true
---

This skill takes the current conversation context and codebase understanding and produces a spec. Do NOT interview the user — just synthesize what you already know.

This project tracks work as **local files** — no remote issue tracker. Specs go to `.scratch/<feature-slug>/spec.md`, next to the tickets `/to-tickets` writes to `.scratch/<feature-slug>/issues/`. The only triage label is `ready-for-agent`.

<!-- markdownlint-disable -->
## Process

1. **Check for an existing `spec.md` first.** Before synthesizing from the conversation, look for this feature under `docs/features/<date>-<feature-slug>/spec.md` (produced by `spec-plan-writer`), matching on feature name/slug.

   - If an **approved** `spec.md` is found, it's the source of truth — don't re-synthesize the Problem Statement or Implementation Decisions from the conversation. Map its content into the template below instead: its Functional Requirements feed Problem Statement + User Stories (rephrase requirements as "As a \<actor\>, I want..." if they aren't already), its Design/Architecture Decisions feed Implementation Decisions, its Edge Cases/Security sections feed Testing Decisions and Further Notes. Only pull from the live conversation for things the spec.md doesn't cover.
   - If a `spec.md` exists but is still `Draft`, tell the user it isn't approved yet and ask whether to proceed anyway or wait.
   - If no `spec.md` exists for this feature, skip straight to step 2 and synthesize from the conversation as usual.

2. Explore the repo to understand the current state of the codebase, if you haven't already. Use the project's domain glossary vocabulary throughout the spec, and respect any ADRs in the area you're touching.

3. Sketch out the seams at which you're going to test the feature. Existing seams should be preferred to new ones. Use the highest seam possible. If new seams are needed, propose them at the highest point you can. The fewer seams across the codebase, the better - the ideal number is one.

Check with the user that these seams match their expectations.

4. Write the spec using the template below to `.scratch/<feature-slug>/spec.md` (create the folder if needed; reuse the slug of the `docs/features/` folder when one exists). Start the file with a `**Status:** ready-for-agent` line - no need for additional triage. Never write to `docs/features/*/spec.md` — that file belongs to `spec-plan-writer`.

<spec-template>

## Problem Statement

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

A LONG, numbered list of user stories. Each user story should be in the format of:

1. As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As a mobile bank customer, I want to see balance on my accounts, so that I can make better informed decisions about my spending
</user-story-example>

This list of user stories should be extremely extensive and cover all aspects of the feature.

## Implementation Decisions

A list of implementation decisions that were made. This can include:

- The modules that will be built/modified
- The interfaces of those modules that will be modified
- Technical clarifications from the developer
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Do NOT include specific file paths or code snippets. They may end up being outdated very quickly.

Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it within the relevant decision and note briefly that it came from a prototype. Trim to the decision-rich parts — not a working demo, just the important bits.

## Testing Decisions

A list of testing decisions that were made. Include:

- A description of what makes a good test (only test external behavior, not implementation details)
- Which modules will be tested
- Prior art for the tests (i.e. similar types of tests in the codebase)

## Out of Scope

A description of the things that are out of scope for this spec.

## Further Notes

Any further notes about the feature.

</spec-template>
