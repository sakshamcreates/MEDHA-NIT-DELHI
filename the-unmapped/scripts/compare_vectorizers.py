#!/usr/bin/env python3
"""Intrinsic vectorizer/config comparison (engineering diagnostics, NOT the claim test).

Task: for each of the 820 occupations, query with its own chunk_text and rank
the 241 skills; gold = the occupation's 10 required_skills.
Metrics: recall@10, MRR (mean over the 10 gold skills).

IMPORTANT CAVEAT: skill context documents are built FROM occupation chunk_texts,
so absolute scores are inflated by circularity. This experiment is valid ONLY for
*relative* comparison of vectorizer configurations, never as a performance claim.
The card.md claim is evaluated separately on human-reviewed held-out labels.

Saves JSON report to data/evaluation/reports/vectorizer_comparison.json
(includes the caveat).
"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np

from engine.extract import ExtractorConfig, SkillExtractor, _clean
from engine.keyword_baseline import load_terms, extract_skills as baseline_extract
RAW_CSV = ROOT / "data" / "raw" / "indian_skills_dataset.csv"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "data" / "evaluation" / "reports"

CAVEAT = ("Intrinsic diagnostic only: skill context docs derive from occupation "
          "chunk_texts, inflating absolute scores. Valid for relative config "
          "comparison, NOT as a performance claim.")


def load_occupations():
    occs = []
    with RAW_CSV.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            occs.append({
                "id": r["id"].strip(),
                "chunk": _clean((r["chunk_text"] or "").strip()),
                "skills": [s.strip() for s in json.loads(r["required_skills"])],
            })
    return occs


def evaluate_extractor(ext: SkillExtractor, occs, label_to_id, k: int = 10):
    recalls, mrrs = [], []
    for occ in occs:
        q = ext.vectorizer.transform([occ["chunk"]])
        from sklearn.metrics.pairwise import cosine_similarity
        s_label = cosine_similarity(q, ext._label_matrix)[0]
        s_occ = cosine_similarity(q, ext._occ_matrix)[0]
        if ext.config.ctx_mode == "maxpool":
            s_ctx = np.array([s_occ[idxs].max() if idxs else 0.0
                              for idxs in ext.skill_occ_idx])
        else:
            s_ctx = cosine_similarity(q, ext._ctx_matrix)[0]
        scores = ext.config.w_label * s_label + ext.config.w_ctx * s_ctx
        ranked = np.argsort(-scores, kind="stable")
        gold = {label_to_id[s] for s in occ["skills"]}
        topk = {ext.skill_ids[i] for i in ranked[:k]}
        recalls.append(len(gold & topk) / len(gold))
        rr = [1.0 / (np.where(ranked == ext.skill_ids.index(g))[0][0] + 1)
              for g in gold]
        mrrs.append(float(np.mean(rr)))
    return float(np.mean(recalls)), float(np.mean(mrrs))


def evaluate_baseline(occs, label_to_id, terms, k: int = 10):
    # baseline has no ranking; treat all matches as rank-tied at top
    recalls = []
    for occ in occs:
        preds = baseline_extract(occ["chunk"], terms)
        pred_ids = [p["skill_id"] for p in preds][:k]
        gold = {label_to_id[s] for s in occ["skills"]}
        recalls.append(len(set(pred_ids) & gold) / len(gold))
    return float(np.mean(recalls)), None


def main() -> None:
    occs = load_occupations()
    label_to_id = {}
    with (PROCESSED / "skill_registry.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            label_to_id[r["label"]] = r["skill_id"]
    terms = load_terms(PROCESSED)

    configs = []
    for vec in ("word", "char", "wordchar"):
        for ctx in ("concat", "maxpool"):
            configs.append(ExtractorConfig(vectorizer=vec, ctx_mode=ctx,
                                           w_label=0.6, w_ctx=0.4))
    results = []
    for cfg in configs:
        t0 = time.time()
        ext = SkillExtractor.build(RAW_CSV, PROCESSED, cfg)
        r10, mrr = evaluate_extractor(ext, occs, label_to_id)
        # score distribution of top-1 scores (informs threshold choice)
        results.append({
            "vectorizer": cfg.vectorizer, "ctx_mode": cfg.ctx_mode,
            "w_label": cfg.w_label, "w_ctx": cfg.w_ctx,
            "recall@10": round(r10, 4), "mrr": round(mrr, 4),
            "build_s": round(time.time() - t0, 1),
        })
        print(f"{cfg.vectorizer:9s} {cfg.ctx_mode:8s} recall@10={r10:.4f} mrr={mrr:.4f}",
              flush=True)
    b_r10, _ = evaluate_baseline(occs, label_to_id, terms)
    results.append({"vectorizer": "keyword_baseline", "ctx_mode": "-",
                    "recall@10": round(b_r10, 4), "mrr": None})
    print(f"keyword_baseline recall@10={b_r10:.4f} (no ranking)")

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "vectorizer_comparison.json"
    out.write_text(json.dumps(
        {"caveat": CAVEAT, "n_occupations": len(occs), "results": results},
        indent=2), encoding="utf-8")
    print(f"\nsaved {out}\nCAVEAT: {CAVEAT}")


if __name__ == "__main__":
    main()
