#!/usr/bin/env python3
"""Evaluation harness: keyword baseline vs TF-IDF extractor.

RULES (card.md claim):
- The claim comparison runs ONLY on human-reviewed ground truth
  (review_status in {approved, corrected}). With zero reviewed labels the
  harness refuses to report a comparison (exit 2) -- it will not fabricate one.
- --diagnostics runs the *intrinsic* chunk_text experiment for both systems.
  Those numbers are engineering diagnostics, never the claim test.
- The same examples are used for both systems. No tuning on the final set.

Writes JSON reports to data/evaluation/reports/ (never overwrites the pilot).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np

from engine.extract import ExtractorConfig, SkillExtractor
from engine.keyword_baseline import extract_skills as baseline_extract
from engine.keyword_baseline import load_terms

RAW_CSV = ROOT / "data" / "raw" / "indian_skills_dataset.csv"
PROCESSED = ROOT / "data" / "processed"
PILOT = ROOT / "data" / "evaluation" / "pilot_descriptions.jsonl"
REVIEWS = ROOT / "data" / "evaluation" / "pilot_reviews.jsonl"
REPORTS = ROOT / "data" / "evaluation" / "reports"

REVIEWED = {"approved", "corrected"}


def load_pilot():
    with PILOT.open(encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def load_reviewed_examples(manifest: dict | None = None,
                           split: str = "test") -> tuple[list[dict], dict]:
    """Build the labeled set from HUMAN reviews only.

    pilot_descriptions.jsonl is never mutated; decisions come from
    pilot_reviews.jsonl. Returns (examples, meta). Raises SystemExit(2)
    when no reviewed labels exist.
    """
    from scripts.review_pilot import load_reviews, reviewed_label_set
    pilot = load_pilot()
    by_id = {r["example_id"]: r for r in pilot}
    labeled = reviewed_label_set(pilot, load_reviews(REVIEWS))
    meta: dict = {"label_source": "pilot_reviews.jsonl (human decisions only)",
                  "n_reviewed_pool": len(labeled)}
    if manifest:
        want = set(manifest.get(f"{split}_ids", []))
        labeled = {k: v for k, v in labeled.items() if k in want}
        meta["manifest"] = manifest.get("version")
        meta["split"] = split
        # version integrity: warn if current data differs from manifest
        for key, path in (("data_checksum", RAW_CSV),
                          ("reviews_checksum", REVIEWS)):
            if manifest.get(key) and _md5(path) != manifest[key]:
                print(f"WARNING: {path.name} changed since manifest "
                      f"{manifest.get('version')} was locked", file=sys.stderr)
    examples = [{"example_id": ex_id,
                 "description": by_id[ex_id]["description"],
                 "expected_skills": skills}
                for ex_id, skills in sorted(labeled.items())]
    if not examples:
        print("REFUSAL: 0 reviewed labels available. No comparison will be reported. "
              "Complete human review per data/evaluation/ANNOTATION_GUIDE.md using "
              "scripts/review_pilot.py, or use --diagnostics for engineering smoke "
              "tests only.", file=sys.stderr)
        raise SystemExit(2)
    return examples, meta


def _md5(path: Path) -> str:
    import hashlib
    return hashlib.md5(path.read_bytes()).hexdigest()


def prf(tp: int, fp: int, fn: int):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4),
            "tp": tp, "fp": fp, "fn": fn}


def evaluate_on_labeled(examples, ext: SkillExtractor, terms, top_k: int,
                        thresholds: list[float]) -> dict:
    """Full comparison on labeled examples. Returns metrics dict."""
    base_tp = base_fp = base_fn = 0
    per_example = []
    skill_stats: dict[str, dict] = {}
    # threshold sweep for the tfidf engine
    sweep = {t: {"tp": 0, "fp": 0, "fn": 0, "abstained": 0} for t in thresholds}

    for rec in examples:
        text = rec["description"]
        gold = {s["skill_id"]: s for s in rec["expected_skills"]}
        gold_ids = set(gold)

        b_pred = {p["skill_id"] for p in baseline_extract(text, terms)}
        base_tp += len(b_pred & gold_ids)
        base_fp += len(b_pred - gold_ids)
        base_fn += len(gold_ids - b_pred)

        out = ext.extract_skills(text, top_k=top_k)
        t_pred = {p["skill_id"]: p for p in out["skills"]}
        t_pred_ids = set(t_pred)
        tp, fp, fn = len(t_pred_ids & gold_ids), len(t_pred_ids - gold_ids), len(gold_ids - t_pred_ids)
        per_example.append({
            "example_id": rec["example_id"],
            "n_gold": len(gold_ids), "n_pred": len(t_pred_ids),
            "tfidf": prf(tp, fp, fn),
            "baseline": prf(len(b_pred & gold_ids), len(b_pred - gold_ids),
                            len(gold_ids - b_pred)),
            "abstained": out["abstained"],
            "missed_gold": sorted(gold_ids - t_pred_ids),
            "false_positives": sorted(t_pred_ids - gold_ids),
        })
        for sid in gold_ids:
            st = skill_stats.setdefault(sid, {"tp": 0, "fp": 0, "fn": 0,
                                              "label": gold[sid]["skill_label"]})
            if sid in t_pred_ids:
                st["tp"] += 1
            else:
                st["fn"] += 1
        for sid in t_pred_ids - gold_ids:
            st = skill_stats.setdefault(sid, {"tp": 0, "fp": 0, "fn": 0,
                                              "label": t_pred[sid]["label"]})
            st["fp"] += 1

        for t in thresholds:
            s_tp = s_fp = s_fn = 0
            kept = {p["skill_id"] for p in out["skills"] if p["score"] >= t}
            # note: out["skills"] already gated at review_threshold; sweep only raises
            s_tp += len(kept & gold_ids); s_fp += len(kept - gold_ids); s_fn += len(gold_ids - kept)
            sw = sweep[t]
            sw["tp"] += s_tp; sw["fp"] += s_fp; sw["fn"] += s_fn
            if not kept:
                sw["abstained"] += 1

    skill_table = []
    for sid, st in sorted(skill_stats.items()):
        m = prf(st["tp"], st["fp"], st["fn"])
        m.update({"skill_id": sid, "label": st["label"],
                  "support": st["tp"] + st["fn"]})
        skill_table.append(m)
    skill_table.sort(key=lambda r: r["support"], reverse=True)

    return {
        "n_examples": len(examples),
        "baseline_micro": prf(base_tp, base_fp, base_fn),
        "tfidf_micro": prf(sum(p["tfidf"]["tp"] for p in per_example),
                            sum(p["tfidf"]["fp"] for p in per_example),
                            sum(p["tfidf"]["fn"] for p in per_example)),
        "per_example": per_example,
        "skill_level": skill_table,
        "threshold_sweep": [
            {"threshold": t, **prf(s["tp"], s["fp"], s["fn"]),
             "abstention_rate": round(s["abstained"] / len(examples), 4)}
            for t, s in sorted(sweep.items())
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate baseline vs TF-IDF extractor.")
    ap.add_argument("--diagnostics", action="store_true",
                    help="intrinsic chunk_text diagnostics (not the claim test)")
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--output", default=None)
    ap.add_argument("--manifest", default=None,
                    help="held-out manifest JSON; evaluates only that split")
    ap.add_argument("--split", default="test", choices=["dev", "test"])
    args = ap.parse_args()

    if args.diagnostics:
        from scripts.compare_vectorizers import (CAVEAT, evaluate_baseline,
                                                 evaluate_extractor, load_occupations)
        occs = load_occupations()
        label_to_id = {}
        with (PROCESSED / "skill_registry.csv").open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                label_to_id[r["label"]] = r["skill_id"]
        ext = SkillExtractor.build(RAW_CSV, PROCESSED, ExtractorConfig())
        r10, mrr = evaluate_extractor(ext, occs, label_to_id)
        b_r10, _ = evaluate_baseline(occs, label_to_id, load_terms(PROCESSED))
        report = {"mode": "diagnostics", "caveat": CAVEAT,
                  "tfidf": {"recall@10": r10, "mrr": mrr},
                  "baseline": {"recall@10": b_r10}}
        print(json.dumps(report, indent=2))
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / "extractor_diagnostics.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8")
        return

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8")) \
        if args.manifest else None
    examples, meta = load_reviewed_examples(manifest, args.split)

    print(f"evaluating on {len(examples)} REVIEWED examples "
          f"[source: {meta['label_source']}]"
          + (f" [manifest {meta['manifest']} split {meta['split']}]" if manifest else ""),
          flush=True)
    if len(examples) < 30:
        print("WARNING: n < 30 -- sample too small for a defensible claim conclusion; "
              "treat as preliminary.", file=sys.stderr)
    ext = SkillExtractor.build(RAW_CSV, PROCESSED, ExtractorConfig())
    terms = load_terms(PROCESSED)
    report = evaluate_on_labeled(examples, ext, terms, args.top_k,
                                 thresholds=[0.05, 0.10, 0.15, 0.20, 0.30, 0.40])
    report["label_source"] = meta
    report["claim_thresholds"] = {"micro_f1_min": 0.50, "margin_over_baseline": 0.10,
                                  "note": "proposed, per card.md"}
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = Path(args.output) if args.output else REPORTS / "extractor_evaluation.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"n_examples": report["n_examples"],
                      "baseline_micro": report["baseline_micro"],
                      "tfidf_micro": report["tfidf_micro"],
                      "threshold_sweep": report["threshold_sweep"]}, indent=2))
    print(f"\nfull report -> {out}")


if __name__ == "__main__":
    main()
