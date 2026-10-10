# Pilot Annotation Guide

**File:** `data/evaluation/pilot_descriptions.jsonl`
**Purpose:** human validation of the 30 synthetic pilot descriptions before they are used
to calibrate the card.md claim threshold. The pilot is NOT the final held-out set.

## What the reviewer checks per example

1. **Description realism** — does it read like a genuine informal self-description from the
   Indian labour market (family business, informal jobs, self-taught skills)? Flag anything
   that sounds templated, contradictory, or implausible.
2. **Skill labels** — for each entry in `expected_skills`:
   - Is the skill genuinely evidenced by the description? Remove it if not.
   - Is any clearly-evidenced skill missing? Add it with `skill_id`, `skill_label`,
     and an exact `evidence_span`.
   - Labels must come from the canonical registry (`data/processed/skill_registry.csv`).
     Never invent a skill label.
3. **Evidence spans** — each `evidence_span` must be an *exact, verbatim substring* of
   `description` (case-sensitive). Prefer the shortest phrase that supports the skill.
   One span per skill; if a skill is evidenced twice, keep the clearest mention.
4. **Target occupation** — is `target_occupation_id` a plausible aspiration given the
   description? It need not be the person's current job; it is the role family the
   example is relevant to. Change it only if clearly wrong (must be a real id from
   `data/raw/indian_skills_dataset.csv`).

## Ambiguous cases — rules

- **Near-duplicate skills** (e.g. `Communication` vs `Client Communication`, `Accounting`
  vs `Financial Accounting`): label the *most specific* skill the evidence supports.
  If the evidence is genuinely generic ("I talk to people"), use the generic one.
  Record the dilemma in `reviewer_notes`; do not label both for the same span.
- **Implied but unstated skills**: label only what the text supports. "I worked in a shop"
  alone is not evidence of `Inventory Management`; "I updated the stock register" is.
- **Informal shorthands** ("Tally", "Excel"): these are covered by approved aliases in
  `data/processed/skill_aliases.csv`. Label the canonical skill.
- **Uncertain**: keep the skill but set `review_status` to `corrected` and explain in
  `reviewer_notes`. Never silently drop a hard case.

## Workflow

1. Reviewer edits the JSONL directly (one JSON object per line; keep `example_id` stable).
2. Set `review_status` to `approved` (no changes needed) or `corrected` (changed labels,
   spans, or occupation). Never leave `pending` after review.
3. Write a one-line summary per changed example in `reviewer_notes`.
4. When all 30 are reviewed, record the date, reviewer name, and Cohen's kappa (if
   double-annotated) in `docs/phase-1-evaluation-plan.md` Phase 2 section.

## What the pilot is NOT

- Not real user data: every record has `"synthetic": true`.
- Not the final held-out test set: the final set (100–120 descriptions) is built *after*
  the pilot, using lessons from this review, and is locked before any model tuning.
