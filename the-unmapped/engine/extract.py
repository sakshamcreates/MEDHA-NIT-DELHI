"""TF-IDF-based Skills Signal Engine (intervention for the card.md claim).

Genuine NLP/ML pipeline: scikit-learn TF-IDF vectorization + cosine similarity
over two channels per skill:

  1. label channel   - canonical label + approved aliases
  2. context channel - concatenated occupation chunk_texts of occupations
                       that require the skill (real dataset text)

score(skill) = w_label * cosine(query, label_doc)
             + w_ctx   * cosine(query, context_doc)

Every prediction carries: canonical ID, similarity score (NOT a calibrated
probability), prediction method, evidence (exact character offsets for direct
phrase matches; explicit "contextual inference" otherwise - never fabricated
spans), confidence/review status, and supporting occupational context.

The keyword baseline (engine/keyword_baseline.py) is untouched and remains
the independent control system.
"""
from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from engine.keyword_baseline import load_terms as _load_baseline_terms

MODEL_NAME = "tfidf-skill-extractor"
MODEL_VERSION = "0.1.0"
MAX_INPUT_CHARS = 5000

REQUIRED_RAW_COLUMNS = {"id", "title", "domain", "chunk_text", "required_skills"}
# education_required / riasec_*: present in the dataset but categorical, not text.
# v0.1.0 deliberately excludes them from the TF-IDF space (not demonstrably
# useful for text similarity); documented in docs/phase-3-model-report.md.


def _clean(text: str) -> str:
    text = text.casefold()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@dataclass
class ExtractorConfig:
    """All knobs in one place; serialized with the model for reproducibility."""
    vectorizer: str = "char"          # "word" | "char" | "wordchar"; char won the
                                      # provisional task-representative comparison
    word_ngram: tuple = (1, 2)
    char_ngram: tuple = (3, 5)
    w_label: float = 0.6
    w_ctx: float = 0.4
    high_threshold: float = 0.20      # provisional: band precision 1.00 on pilot
    review_threshold: float = 0.10    # provisional: band precision 0.30-0.53
    ambiguity_margin: float = 0.05
    sublinear_tf: bool = True
    ctx_mode: str = "maxpool"         # "concat" | "maxpool"; maxpool won the
                                      # intrinsic comparison (see model report)

    def describe(self) -> dict:
        return {
            "vectorizer": self.vectorizer,
            "word_ngram": list(self.word_ngram),
            "char_ngram": list(self.char_ngram),
            "w_label": self.w_label,
            "w_ctx": self.w_ctx,
            "high_threshold": self.high_threshold,
            "review_threshold": self.review_threshold,
            "ctx_mode": self.ctx_mode,
        }


def _make_vectorizer(cfg: ExtractorConfig) -> TfidfVectorizer:
    if cfg.vectorizer == "word":
        return TfidfVectorizer(analyzer="word", ngram_range=cfg.word_ngram,
                               sublinear_tf=cfg.sublinear_tf, min_df=1)
    if cfg.vectorizer == "char":
        return TfidfVectorizer(analyzer="char_wb", ngram_range=cfg.char_ngram,
                               sublinear_tf=cfg.sublinear_tf, min_df=1)
    if cfg.vectorizer == "wordchar":
        from sklearn.pipeline import FeatureUnion
        return FeatureUnion([
            ("word", TfidfVectorizer(analyzer="word", ngram_range=cfg.word_ngram,
                                    sublinear_tf=cfg.sublinear_tf, min_df=1)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=cfg.char_ngram,
                                     sublinear_tf=cfg.sublinear_tf, min_df=1)),
        ])
    raise ValueError(f"unknown vectorizer: {cfg.vectorizer}")


class SkillExtractor:
    def __init__(self, config: ExtractorConfig | None = None):
        self.config = config or ExtractorConfig()
        self.vectorizer = None
        # fitted state
        self.skill_ids: list[str] = []
        self.skill_labels: list[str] = []
        self.skill_occ_idx: list[list[int]] = []
        self._label_matrix = None
        self._ctx_matrix = None
        self._occ_matrix = None
        self.occ_ids: list[str] = []
        self.occ_titles: list[str] = []
        self.ambiguous_pairs: set[frozenset] = set()
        self._phrase_terms = None
        self.data_checksum = ""
        self.n_occupations = 0

    # ------------------------------------------------------------------ build
    @classmethod
    def build(cls, raw_csv: str | Path, processed_dir: str | Path,
              config: ExtractorConfig | None = None) -> "SkillExtractor":
        raw_csv, processed_dir = Path(raw_csv), Path(processed_dir)
        if not raw_csv.exists():
            raise FileNotFoundError(f"raw dataset not found: {raw_csv}")
        ext = cls(config)
        with raw_csv.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            missing = REQUIRED_RAW_COLUMNS - set(reader.fieldnames or [])
            if missing:
                raise ValueError(
                    f"raw dataset missing required columns: {sorted(missing)} "
                    f"(found: {reader.fieldnames})")
            rows = list(reader)
        if not rows:
            raise ValueError("raw dataset is empty")
        ext.data_checksum = hashlib.md5(raw_csv.read_bytes()).hexdigest()
        ext.n_occupations = len(rows)

        # registry
        reg: dict[str, str] = {}
        with (processed_dir / "skill_registry.csv").open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                reg[r["label"]] = r["skill_id"]
        if not reg:
            raise ValueError("skill registry is empty")
        # approved aliases -> skill
        aliases: dict[str, list[str]] = {}
        with (processed_dir / "skill_aliases.csv").open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["status"].strip().lower() != "approved":
                    continue
                aliases.setdefault(r["canonical_label"], []).append(r["alias"])
        # occupation -> skills, skill -> chunk_texts
        import json
        skill_chunks: dict[str, list[str]] = {lab: [] for lab in reg}
        skill_occ_idx: dict[str, list[int]] = {lab: [] for lab in reg}
        occ_docs: list[str] = []
        for r in rows:
            chunk = (r["chunk_text"] or "").strip()
            if not chunk:
                raise ValueError(f"occupation {r['id']!r} has empty chunk_text")
            occ_index = len(ext.occ_ids)
            ext.occ_ids.append(r["id"].strip())
            ext.occ_titles.append(r["title"].strip())
            occ_docs.append(_clean(chunk))
            for raw_skill in json.loads(r["required_skills"]):
                label = re.sub(r"\s+", " ", raw_skill.strip())
                if label not in reg:
                    raise ValueError(f"skill {label!r} not in registry")
                skill_chunks[label].append(_clean(chunk))
                skill_occ_idx[label].append(occ_index)

        # review-queue ambiguous pairs (kept separate; flagged, never merged)
        with (processed_dir / "skill_review_queue.csv").open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["status"].strip().lower() == "open":
                    ext.ambiguous_pairs.add(
                        frozenset({r["skill_a_id"], r["skill_b_id"]}))

        labels_sorted = sorted(reg, key=lambda s: (s.lower(), s))
        ext.skill_ids = [reg[l] for l in labels_sorted]
        ext.skill_labels = labels_sorted
        ext.skill_occ_idx = [skill_occ_idx[l] for l in labels_sorted]
        label_docs = [_clean(" ".join([l] + aliases.get(l, []))) for l in labels_sorted]
        ctx_docs = [" ".join(skill_chunks[l]) for l in labels_sorted]

        ext.vectorizer = _make_vectorizer(ext.config)
        all_docs = label_docs + ctx_docs + occ_docs
        ext.vectorizer.fit(all_docs)
        ext._label_matrix = ext.vectorizer.transform(label_docs)
        ext._ctx_matrix = ext.vectorizer.transform(ctx_docs)
        ext._occ_matrix = ext.vectorizer.transform(occ_docs)
        ext._phrase_terms = _load_baseline_terms(processed_dir)
        return ext

    # ------------------------------------------------------------------ save
    def save(self, path: str | Path) -> None:
        joblib.dump({
            "model_name": MODEL_NAME, "model_version": MODEL_VERSION,
            "config": self.config,
            "vectorizer": self.vectorizer,
            "skill_ids": self.skill_ids, "skill_labels": self.skill_labels,
            "skill_occ_idx": self.skill_occ_idx,
            "label_matrix": self._label_matrix, "ctx_matrix": self._ctx_matrix,
            "occ_matrix": self._occ_matrix,
            "occ_ids": self.occ_ids, "occ_titles": self.occ_titles,
            "ambiguous_pairs": self.ambiguous_pairs,
            "phrase_terms": self._phrase_terms,
            "data_checksum": self.data_checksum,
            "n_occupations": self.n_occupations,
        }, path)

    @classmethod
    def load(cls, path: str | Path) -> "SkillExtractor":
        d = joblib.load(path)
        ext = cls(d["config"])
        ext.vectorizer = d["vectorizer"]
        ext.skill_ids = d["skill_ids"]
        ext.skill_labels = d["skill_labels"]
        ext.skill_occ_idx = d["skill_occ_idx"]
        ext._label_matrix = d["label_matrix"]
        ext._ctx_matrix = d["ctx_matrix"]
        ext._occ_matrix = d["occ_matrix"]
        ext.occ_ids = d["occ_ids"]
        ext.occ_titles = d["occ_titles"]
        ext.ambiguous_pairs = d["ambiguous_pairs"]
        ext._phrase_terms = d["phrase_terms"]
        ext.data_checksum = d["data_checksum"]
        ext.n_occupations = d["n_occupations"]
        return ext

    # ---------------------------------------------------------------- extract
    def _phrase_hits(self, text: str) -> dict[str, tuple[str, int, int]]:
        """skill_id -> (span, start, end): longest-match-wins, deterministic."""
        from engine.keyword_baseline import _compile
        folded = text.casefold()
        raw = []
        for term in self._phrase_terms:
            for m in _compile(term.term).finditer(folded):
                raw.append((m.start(), m.end(), term))
        raw.sort(key=lambda r: (r[0], -(r[1] - r[0]), r[2].skill_id))
        accepted: dict[str, tuple[str, int, int]] = {}
        spans: list[tuple[int, int]] = []
        for s, e, term in raw:
            if any(s < ae and e > a_ for a_, ae in spans):
                continue
            spans.append((s, e))
            if term.skill_id not in accepted:  # longest match already won
                accepted[term.skill_id] = (text[s:e], s, e)
        return accepted

    def extract_skills(self, text: str, top_k: int = 10) -> dict:
        if not isinstance(text, str):
            raise TypeError(f"text must be str, got {type(text).__name__}")
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            raise ValueError(f"top_k must be a positive int, got {top_k!r}")
        if len(text) > MAX_INPUT_CHARS:
            raise ValueError(
                f"input too long: {len(text)} chars (max {MAX_INPUT_CHARS})")
        warnings: list[str] = []
        if not text.strip():
            return self._empty_result(top_k, warnings, "empty_input")
        if len(text.strip()) < 15:
            warnings.append("very_short_input: results may be unreliable")

        q = self.vectorizer.transform([_clean(text)])
        cfg = self.config
        s_label = cosine_similarity(q, self._label_matrix)[0]
        s_occ = cosine_similarity(q, self._occ_matrix)[0]
        if cfg.ctx_mode == "maxpool":
            s_ctx = np.array([s_occ[idxs].max() if idxs else 0.0
                              for idxs in self.skill_occ_idx])
        elif cfg.ctx_mode == "concat":
            s_ctx = cosine_similarity(q, self._ctx_matrix)[0]
        else:
            raise ValueError(f"unknown ctx_mode: {cfg.ctx_mode}")
        scores = cfg.w_label * s_label + cfg.w_ctx * s_ctx
        top_occ_idx = np.argsort(-s_occ)[:2]

        phrase_hits = self._phrase_hits(text)
        # A literal gazetteer hit (label/approved alias) is first-class evidence:
        # it guarantees candidacy at "review" confidence. TF-IDF ranks among
        # candidates and supplies contextual inferences beyond literal mentions.
        has_phrase = np.array([self.skill_ids[i] in phrase_hits
                               for i in range(len(self.skill_ids))])
        scores = np.maximum(scores, has_phrase * cfg.review_threshold)
        order = np.argsort(-scores, kind="stable")
        predictions: list[dict] = []
        for idx in order:
            score = float(scores[idx])
            if score < cfg.review_threshold or len(predictions) >= top_k:
                # scores are descending; still need ambiguity check on kept ones
                if score < cfg.review_threshold:
                    break
                continue
            sid = self.skill_ids[idx]
            label = self.skill_labels[idx]
            if sid in phrase_hits:
                span, start, end = phrase_hits[sid]
                evidence = {"type": "direct", "span": span,
                            "start": start, "end": end}
                method = "phrase_match"
            else:
                evidence = {"type": "contextual_inference",
                            "note": "no direct phrase match in input; inferred "
                                    "from occupational context"}
                method = "contextual_inference"
            confidence = "high" if score >= cfg.high_threshold else "review"
            predictions.append({
                "skill_id": sid,
                "label": label,
                "score": round(score, 4),
                "method": method,
                "confidence": confidence,
                "evidence": evidence,
                "occupation_context": [
                    {"occupation_id": self.occ_ids[i],
                     "title": self.occ_titles[i],
                     "score": round(float(s_occ[i]), 4)}
                    for i in top_occ_idx
                ],
                "notes": [],
                "_score": score,
            })

        # ambiguity flagging on kept predictions (never merge)
        by_id = {p["skill_id"]: p for p in predictions}
        for pair in self.ambiguous_pairs:
            a, b = tuple(pair)
            if a in by_id and b in by_id:
                if abs(by_id[a]["_score"] - by_id[b]["_score"]) < cfg.ambiguity_margin:
                    for sid in (a, b):
                        by_id[sid]["confidence"] = "review"
                        by_id[sid]["notes"].append(
                            f"ambiguous_with:{a if sid == b else b}: "
                            f"near-duplicate pair under manual review; "
                            f"kept separate, not merged")
        for p in predictions:
            p.pop("_score", None)

        if not predictions:
            return self._empty_result(
                top_k, warnings + ["no predictions passed the review threshold"],
                "no_confident_predictions")
        return {
            "skills": predictions,
            "abstained": False,
            "abstention_reason": None,
            "warnings": warnings,
            "model": self._model_meta(),
            "top_k": top_k,
        }

    def _empty_result(self, top_k: int, warnings: list[str], reason: str) -> dict:
        return {"skills": [], "abstained": True, "abstention_reason": reason,
                "warnings": warnings, "model": self._model_meta(), "top_k": top_k}

    def _model_meta(self) -> dict:
        return {
            "name": MODEL_NAME, "version": MODEL_VERSION,
            "vectorizer": self.config.describe(),
            "data_checksum": self.data_checksum,
            "n_occupations": self.n_occupations,
            "n_skills": len(self.skill_ids),
            "score_note": "cosine similarity in TF-IDF space; NOT a calibrated probability",
        }


# ---------------------------------------------------------------------------
# Module-level interface (lazy singleton built from the real data files)
# ---------------------------------------------------------------------------

_EXTRACTOR: SkillExtractor | None = None


def _default_paths() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parent.parent
    return root / "data" / "raw" / "indian_skills_dataset.csv", root / "data" / "processed"


def get_extractor(config: ExtractorConfig | None = None,
                  rebuild: bool = False) -> SkillExtractor:
    global _EXTRACTOR
    if _EXTRACTOR is None or rebuild:
        raw_csv, processed = _default_paths()
        _EXTRACTOR = SkillExtractor.build(raw_csv, processed, config)
    return _EXTRACTOR


def extract_skills(text: str, top_k: int = 10) -> dict:
    """extract_skills(text, top_k=10) -> dict (see SkillExtractor.extract_skills)."""
    return get_extractor().extract_skills(text, top_k)


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(description="TF-IDF Skills Signal Engine.")
    ap.add_argument("--text", help="input description to analyze")
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--vectorizer", default="word", choices=["word", "char", "wordchar"])
    ap.add_argument("--save", help="save fitted extractor to PATH (joblib)")
    args = ap.parse_args()
    cfg = ExtractorConfig(vectorizer=args.vectorizer)
    raw_csv, processed = _default_paths()
    ext = SkillExtractor.build(raw_csv, processed, cfg)
    if args.save:
        ext.save(args.save)
        print(f"saved to {args.save}")
    if args.text:
        print(json.dumps(ext.extract_skills(args.text, args.top_k),
                         indent=2, ensure_ascii=False))
