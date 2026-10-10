#!/usr/bin/env python3
"""Build the canonical skill registry from the Indian Skills Dataset.

Reads data/raw/indian_skills_dataset.csv and generates deterministic,
reproducible artifacts in data/processed/:

  skill_registry.csv        - 241 canonical skills, SKL-001..SKL-241
  occupation_skill_map.csv  - 8200 occupation -> skill relationships
  skill_aliases.csv         - approved aliases -> canonical skill IDs
  skill_review_queue.csv    - near-duplicate pairs flagged for manual review
  domain_skill_summary.csv  - per-domain skill/salary/demand summary

Design rules (Phase 2 spec):
  - IDs are assigned by sorting normalized labels: stable across runs
    when the vocabulary is unchanged.
  - Related skills are NEVER auto-merged (e.g. Communication vs
    Business Communication). Uncertain pairs go to the review queue.
  - Aliases are only genuine spelling variants or unambiguous synonyms/
    shorthands, each documented with a rationale.
  - No timestamps or run-specific data in outputs: byte-reproducible.

Filename note: Phase 1 architecture proposed JSON artifacts; Phase 2 uses
CSVs for human auditability (documented in docs/phase-1-evaluation-plan.md).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

RAW_CSV = Path("data/raw/indian_skills_dataset.csv")
PROCESSED = Path("data/processed")

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_label(label: str) -> str:
    """Collapse whitespace and strip. Case is preserved in the canonical label;
    matching layers decide their own case policy."""
    return re.sub(r"\s+", " ", label.strip())


# ---------------------------------------------------------------------------
# Approved aliases: (alias_text, canonical_label, alias_type, notes)
# Only genuine spelling variants or unambiguous synonyms/shorthands.
# ---------------------------------------------------------------------------

APPROVED_ALIASES: list[tuple[str, str, str, str]] = [
    (
        "Experiment Design",
        "Experimental Design",
        "spelling_variant",
        "Same concept; adjectival form is the standard term. "
        "Both labels remain in the registry; alias routes the variant.",
    ),
    (
        "tally",
        "Financial Accounting",
        "informal_variant",
        "In Indian small-business context 'Tally' unambiguously means Tally ERP "
        "accounting software; 'did accounts in Tally' implies Financial Accounting.",
    ),
    (
        "excel",
        "Excel/Spreadsheets",
        "informal_variant",
        "Unambiguous shorthand for spreadsheet work; canonical label is Excel/Spreadsheets.",
    ),
    (
        "ms excel",
        "Excel/Spreadsheets",
        "informal_variant",
        "Microsoft Excel; unambiguous.",
    ),
    (
        "spreadsheet",
        "Excel/Spreadsheets",
        "informal_variant",
        "Generic term; the registry's only spreadsheet skill is Excel/Spreadsheets.",
    ),
    (
        "spreadsheets",
        "Excel/Spreadsheets",
        "informal_variant",
        "Plural of spreadsheet; same mapping.",
    ),
]


def token_set(label: str) -> set[str]:
    return set(re.findall(r"[a-z]+", label.lower()))


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build(input_csv: Path, out_dir: Path) -> dict[str, int]:
    df_rows: list[dict] = []
    with input_csv.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            df_rows.append(row)
    assert len(df_rows) == 820, f"expected 820 occupations, got {len(df_rows)}"

    # --- vocabulary ---------------------------------------------------------
    skill_to_occs: dict[str, list[str]] = defaultdict(list)
    occ_info: dict[str, dict] = {}
    for row in df_rows:
        occ_id = row["id"].strip()
        occ_info[occ_id] = {
            "title": row["title"].strip(),
            "domain": row["domain"].strip(),
        }
        for raw in json.loads(row["required_skills"]):
            label = normalize_label(raw)
            assert label, f"empty skill label in occupation {occ_id}"
            skill_to_occs[label].append(occ_id)

    labels = sorted(skill_to_occs, key=lambda s: (s.lower(), s))
    assert len(labels) == 241, f"expected 241 skills, got {len(labels)}"
    skill_id = {label: f"SKL-{i:03d}" for i, label in enumerate(labels, 1)}
    assert len(set(skill_id.values())) == 241, "duplicate skill IDs"

    out_dir.mkdir(parents=True, exist_ok=True)
    stats: dict[str, int] = {}

    # --- 1. skill_registry.csv ----------------------------------------------
    with (out_dir / "skill_registry.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["skill_id", "label", "normalized_label",
                    "occupation_count", "example_occupations", "source"])
        for label in labels:
            occs = sorted(set(skill_to_occs[label]))
            w.writerow([
                skill_id[label], label, normalize_label(label),
                len(occs), "|".join(occs[:3]), "indian_skills_dataset.csv",
            ])
    stats["canonical_skills"] = len(labels)

    # --- 2. occupation_skill_map.csv -----------------------------------------
    with (out_dir / "occupation_skill_map.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["occupation_id", "occupation_title", "domain",
                    "skill_id", "skill_label"])
        n_rel = 0
        for occ_id in sorted(occ_info):
            for row in df_rows:
                if row["id"].strip() != occ_id:
                    continue
                for raw in json.loads(row["required_skills"]):
                    label = normalize_label(raw)
                    w.writerow([occ_id, occ_info[occ_id]["title"],
                                occ_info[occ_id]["domain"],
                                skill_id[label], label])
                    n_rel += 1
                break
    stats["occupation_skill_relationships"] = n_rel
    assert n_rel == 8200, f"expected 8200 relationships, got {n_rel}"

    # --- 3. skill_aliases.csv --------------------------------------------------
    with (out_dir / "skill_aliases.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["alias", "normalized_alias", "skill_id", "canonical_label",
                    "alias_type", "status", "notes"])
        for alias, canonical, atype, notes in sorted(APPROVED_ALIASES):
            assert canonical in skill_id, f"alias target missing: {canonical}"
            w.writerow([alias, normalize_label(alias).lower(),
                        skill_id[canonical], canonical, atype, "approved", notes])
    stats["approved_aliases"] = len(APPROVED_ALIASES)

    # --- 4. skill_review_queue.csv ---------------------------------------------
    pairs: list[tuple[str, str, str, str]] = []
    for a, b in combinations(labels, 2):
        ta, tb = token_set(a), token_set(b)
        jacc = len(ta & tb) / len(ta | tb)
        sub = a.lower() in b.lower() or b.lower() in a.lower()
        if sub or jacc >= 0.5:
            pairs.append((a, b, "substring" if sub else "token_overlap",
                          "|".join(sorted(ta & tb))))
    pairs.sort()
    with (out_dir / "skill_review_queue.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["pair_id", "skill_a_id", "skill_a_label",
                    "skill_b_id", "skill_b_label", "relation",
                    "shared_tokens", "recommendation", "status"])
        for i, (a, b, rel, shared) in enumerate(pairs, 1):
            w.writerow([
                f"REV-{i:03d}", skill_id[a], a, skill_id[b], b, rel, shared,
                "Manual review required: keep separate, merge, or alias. "
                "DO NOT auto-merge; decision affects registry IDs and all labels.",
                "open",
            ])
    stats["review_queue_pairs"] = len(pairs)

    # --- 5. domain_skill_summary.csv ---------------------------------------------
    dom_occs: dict[str, list[dict]] = defaultdict(list)
    for row in df_rows:
        dom_occs[row["domain"].strip()].append(row)
    with (out_dir / "domain_skill_summary.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["domain", "occupation_count", "avg_salary_lpa_median",
                    "demand_emerging", "demand_high_growth", "demand_stable",
                    "demand_very_high_growth", "bright_outlook_count",
                    "top_skills"])
        for domain in sorted(dom_occs):
            rows = dom_occs[domain]
            salaries = [int(r["india_salary_lpa_median"]) for r in rows]
            trends = Counter(r["india_demand_trend"].strip() for r in rows)
            sk = Counter(normalize_label(s)
                         for r in rows for s in json.loads(r["required_skills"]))
            top = "|".join(f"{s} ({c})" for s, c in sk.most_common(5))
            w.writerow([
                domain, len(rows), round(sum(salaries) / len(salaries), 1),
                trends.get("Emerging", 0), trends.get("High Growth", 0),
                trends.get("Stable", 0), trends.get("Very High Growth", 0),
                sum(1 for r in rows if r["bright_outlook"].strip().lower() == "true"),
                top,
            ])
    stats["domains"] = len(dom_occs)

    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the canonical skill registry.")
    ap.add_argument("--input", default=str(RAW_CSV))
    ap.add_argument("--output-dir", default=str(PROCESSED))
    args = ap.parse_args()
    stats = build(Path(args.input), Path(args.output_dir))
    for k, v in stats.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
