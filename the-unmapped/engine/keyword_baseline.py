"""Keyword-matching baseline (control condition for the card.md claim).

Matches canonical skill labels and *approved* aliases against input text with
case-insensitive, word-boundary-aware substring search. No stemming, no TF-IDF,
no aliases beyond skill_aliases.csv with status=approved.

Deterministic overlap resolution: longest match wins; ties broken by skill_id.
Every prediction carries an exact evidence span into the original text.

This module is intentionally separate from the future TF-IDF Skills Signal
Engine so both can be evaluated fairly on the same held-out set.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MatchTerm:
    term: str          # as written (label or alias)
    skill_id: str
    label: str         # canonical label
    source: str        # "label" | "alias"


def load_terms(processed_dir: str | Path) -> list[MatchTerm]:
    processed = Path(processed_dir)
    terms: list[MatchTerm] = []
    with (processed / "skill_registry.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            terms.append(MatchTerm(row["label"], row["skill_id"], row["label"], "label"))
    with (processed / "skill_aliases.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["status"].strip().lower() != "approved":
                continue
            terms.append(MatchTerm(row["alias"], row["skill_id"],
                                   row["canonical_label"], "alias"))
    # Longest-first, then skill_id: deterministic overlap resolution.
    terms.sort(key=lambda t: (-len(t.term), t.skill_id, t.term.lower()))
    return terms


def _compile(term: str) -> re.Pattern:
    # Word-boundary via lookarounds (handles labels containing '/').
    return re.compile(r"(?<![a-z0-9])" + re.escape(term.casefold()) + r"(?![a-z0-9])")


def extract_skills(text: str, terms: list[MatchTerm]) -> list[dict]:
    """Return predictions: [{skill_id, label, span, start, end, source}]."""
    if not isinstance(text, str):
        raise TypeError(f"text must be str, got {type(text).__name__}")
    if not text.strip():
        return []
    folded = text.casefold()
    raw: list[tuple[int, int, MatchTerm]] = []
    for term in terms:
        for m in _compile(term.term).finditer(folded):
            raw.append((m.start(), m.end(), term))
    # Deterministic: earliest start, then longest match, then skill_id.
    raw.sort(key=lambda r: (r[0], -(r[1] - r[0]), r[2].skill_id))
    accepted: list[tuple[int, int, MatchTerm]] = []
    for start, end, term in raw:
        if any(start < a_end and end > a_start for a_start, a_end, _ in accepted):
            continue
        accepted.append((start, end, term))
    accepted.sort(key=lambda r: r[0])
    return [{
        "skill_id": t.skill_id,
        "label": t.label,
        "span": text[s:e],
        "start": s,
        "end": e,
        "source": t.source,
    } for s, e, t in accepted]


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(description="Keyword baseline skill extraction.")
    ap.add_argument("--text", required=True)
    ap.add_argument("--processed-dir", default="data/processed")
    args = ap.parse_args()
    print(json.dumps(extract_skills(args.text, load_terms(args.processed_dir)),
                     indent=2, ensure_ascii=False))
