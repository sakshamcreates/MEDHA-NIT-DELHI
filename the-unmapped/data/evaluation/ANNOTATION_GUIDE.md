# Pilot Annotation Guide (Phase 6)

**Scope:** human validation of the 30 synthetic pilot descriptions in
`data/evaluation/pilot_descriptions.jsonl` before they calibrate the card.md
claim threshold. The pilot is NOT the final held-out set.

**Reviewer:** any domain-literate human. No account system is used; identify
yourself with `--reviewer "Your Name"` (used for versioning and agreement).

## The one rule

`data/evaluation/pilot_descriptions.jsonl` is **never edited**. All decisions go
to `data/evaluation/pilot_reviews.jsonl` (append-only, versioned). The original
synthetic annotations stay intact and every example keeps `review_status: pending`
in the pilot file.

## What you check per example

1. **Description realism** — does it read like a genuine informal self-description
   from the Indian labour market (family business, informal jobs, self-taught
   skills)? Flag anything templated, contradictory, or implausible.
2. **Skill labels** — for each proposed skill:
   - Is it genuinely evidenced by the description? Remove it if not.
   - Is any clearly-evidenced skill missing? Add it (`skill_id`, `skill_label`,
     exact `evidence_span`).
   - Labels must come from `data/processed/skill_registry.csv`. Never invent one.
3. **Evidence spans** — exact, verbatim substrings of the description
   (case-sensitive). Shortest phrase that supports the skill; one span per skill.
4. **Target occupation** — is it a plausible aspiration given the description?
   It need not be the person's current job.

## Ambiguous cases

- **Near-duplicates** (e.g. `Accounting` vs `Financial Accounting`): label the *most
  specific* skill the evidence supports; record the dilemma in notes; never label
  both for the same span.
- **Implied but unstated skills**: label only what the text supports.
- **Informal shorthands** ("Tally", "Excel"): covered by approved aliases in
  `data/processed/skill_aliases.csv`; label the canonical skill.
- **Uncertain**: keep the skill, choose `corrected`, explain in notes. Never
  silently drop a hard case.

## Decisions

- **approve** — proposals are correct as-is.
- **correct** — you changed labels, spans, or added/dropped skills.
- **reject** — the description itself is unusable (implausible/contradictory);
  rejected examples are excluded from evaluation, never silently fixed.
- **skip** — leave for later; the example stays pending.

Re-deciding an example requires `--amend`; the correction is stored as a new
version and the full history is preserved (`review_history`).

## Commands

```bash
# interactive review (30 cases)
.venv/bin/python scripts/review_pilot.py --reviewer "Your Name"
# show current model predictions alongside proposals (reference only, NOT ground truth)
.venv/bin/python scripts/review_pilot.py --reviewer "Your Name" --with-model

# export pending cases for offline/spreadsheet review
.venv/bin/python scripts/review_pilot.py --reviewer "Your Name" --export-csv /tmp/pending.csv
.venv/bin/python scripts/review_pilot.py --reviewer "Your Name" --export-json /tmp/pending.json

# import filled spreadsheet (approve/reject only; corrections need JSON)
.venv/bin/python scripts/review_pilot.py --reviewer "Your Name" --import-csv /tmp/decisions.csv
# import full-fidelity JSON batch (all decision types, incl. corrections)
.venv/bin/python scripts/review_pilot.py --reviewer "Your Name" --batch /tmp/decisions.json
# amend previously recorded decisions (explicit new versions)
.venv/bin/python scripts/review_pilot.py --reviewer "Your Name" --batch /tmp/fixes.json --amend

# status, validation, inter-reviewer agreement
.venv/bin/python scripts/review_report.py
.venv/bin/python scripts/review_report.py --require 30   # gate: exit 2 if unmet
```

Batch/CSV import is **atomic**: one invalid row aborts the whole import with
nothing written. Duplicate decisions without `--amend` are refused.

## After review

- `scripts/review_report.py` validates every record; fix anything it flags invalid.
- With two reviewers on the same examples, the report shows exact-match rate and
  mean pairwise Jaccard (Cohen's-kappa territory; kappa derivable from records).
- If reviewers disagree on an example, the evaluation uses one named reviewer's
  set (`--reviewer`); there is no silent adjudication.
- Only when 30 valid reviews exist may the held-out set be locked
  (`scripts/make_heldout.py`) and the claim comparison run
  (`scripts/evaluate_extractor.py`).

## What the pilot is NOT

- Not real user data: every record has `"synthetic": true`.
- Not the final held-out test set: built *after* the pilot, locked before tuning.
- Model predictions shown with `--with-model` are reference only, never labels.
