# Phase 3 — Model Report: TF-IDF Skills Signal Engine

**Date:** 2026-10-10 · **Model:** `tfidf-skill-extractor` v0.1.0 · **Status:** implemented, tested, NOT claim-validated (no reviewed labels exist yet)

> Nothing in this report is the card.md claim test. All F1 numbers below are
> provisional diagnostics on unreviewed synthetic pilot labels or intrinsic
> retrieval checks, clearly labeled as such.

---

## 1. Architecture

`engine/extract.py` — scikit-learn TF-IDF + cosine similarity, two channels per skill:

```
score(skill) = 0.6 * cosine(query, label_doc) + 0.4 * cosine(query, context_doc)
label_doc    = canonical label + approved aliases
context_doc  = occupation chunk_texts, max-pooled: max over occupations
               having the skill of cosine(query, occupation chunk_text)
```

- **Corpus:** 241 label docs + 241 context docs + 820 occupation docs (real dataset text).
- **Phrase floor:** a literal gazetteer hit (label/approved alias) guarantees candidacy at
  `review` confidence — the gazetteer is first-class evidence, TF-IDF ranks and infers beyond it.
- **Evidence:** direct phrase matches carry exact character offsets; contextual inferences
  carry NO spans (explicitly labeled, never fabricated).
- **Gates:** score ≥ 0.20 → `high`; 0.10–0.20 → `review`; below → dropped. No confident
  predictions → abstention with reason. Scores are cosine similarities, **not** calibrated
  probabilities (stated in every response's model metadata).
- **Ambiguity:** the 41 review-queue near-duplicate pairs are never merged; co-predicted
  pairs within 0.05 are both forced to `review` with an `ambiguous_with:` note.
- **Education/RIASEC:** deliberately excluded from v0.1.0 — categorical fields, not text;
  not demonstrably useful for text similarity. Reserved for the recommender (Component B).

## 2. Configurations evaluated (reproducible experiments)

### 2a. Intrinsic retrieval diagnostic — chunk_text → own 10 skills (n=820)

Caveat: context docs derive from chunk_texts, so absolute numbers are inflated; valid
for *relative* config comparison only. Full table in
`data/evaluation/reports/vectorizer_comparison.json`.

| Vectorizer | Context | recall@10 | MRR | build time |
|---|---|---|---|---|
| word 1–2gram | maxpool | **1.000** | 0.293 | 10 s |
| word 1–2gram | concat | 0.990 | 0.293 | 14 s |
| char 3–5gram | maxpool | 1.000 | 0.293 | 61 s |
| char 3–5gram | concat | 0.862 | 0.286 | 69 s |
| word+char | maxpool | 1.000 | 0.293 | 94 s |
| keyword baseline | — | 0.643 | — | — |

**Decisions from evidence:** maxpool beats concat on every vectorizer (occupation context
matters — consistent with the Phase 1 audit finding); word/maxpool chosen over char
variants for the intrinsic ranking task on build-time grounds (6–9× faster, equal MRR).

### 2b. Task-representative provisional sweep — 30 pilot descriptions vs synthetic labels

Ungated top-10 ranking, thresholds swept (provisional labels — direction signal only):

| Config | best thr | P | R | F1 |
|---|---|---|---|---|
| word / maxpool | 0.03 | 0.176 | 0.359 | 0.237 |
| **char / maxpool** | **0.10** | **0.361** | **0.299** | **0.327** |
| keyword baseline | — | 0.750 | 0.077 | 0.140 |

**Decision from evidence:** char n-grams handle morphological variation
("accounts"→Accounting, "taught"→Teaching) that word unigrams miss on paraphrased
informal text. **Default config: char 3–5gram + maxpool**, w_label=0.6/w_ctx=0.4.
The word model (F1 0.237) barely beats the baseline (0.140) — reported honestly:
word-level TF-IDF does not reliably improve over substring matching on paraphrase.

### 2c. Gate calibration (provisional pilot bands)

| Score band | n | provisional precision |
|---|---|---|
| ≥ 0.20 (`high`) | 4 | 1.00 |
| 0.10–0.20 (`review`) | 95 | 0.30–0.53 |

Gates set at high=0.20 / review=0.10. Provisional — will be re-tuned on reviewed labels.

## 3. Data sizes

- Fit corpus: 1,302 documents (241 + 241 + 820), from `indian_skills_dataset.csv` (md5 recorded in model metadata).
- Provisional eval: 30 synthetic descriptions, 117 annotations (all `pending` review).
- Reviewed eval: **0 examples — the claim test has not run.**

## 4. How occupation context contributes

Max-pooling over per-occupation similarities (rather than one giant concatenated doc)
raised intrinsic recall@10 from 0.86–0.99 → 1.00 across vectorizers. Every prediction
also returns the top-2 matching occupations as supporting context (e.g. PILOT-011's
inferences cite "Pesticide Handlers, Sprayers, and Applicators, Vegetation").

## 5. Error analysis (smoke-test inputs — synthetic, unreviewed)

**PILOT-001** (family-business accounts): TP Financial Accounting (via "Tally" alias),
TP Excel/Spreadsheets (via "Excel" alias, phrase floor); FP Accounting co-predicted and
correctly flagged `ambiguous_with` (kept separate, both `review`). Missed Data Entry,
Taxation, Record Keeping — pure paraphrases ("entered every sale", "filed the GST
returns") with no lexical bridge.

**PILOT-011** (farming): TP Soil Analysis ← "test the soil by hand", TP Pest Management
← "spray pesticides" (genuine contextual inferences, no literal labels). FP Scheduling
← char n-gram artifact of "schedule"; FP Soil Science (near-duplicate of Soil Analysis
*not* caught by the review-queue heuristic — token-Jaccard 0.33, listed as a queue
recall gap); FP Time Management. Missed Agronomy, Irrigation.

**Failure categories:** (1) true paraphrase with zero lexical overlap — TF-IDF cannot
bridge these; (2) char n-gram spurious matches on morphological fragments; (3)
near-duplicate skills outside the 41 flagged pairs; (4) generic-skill dominance is
reduced vs baseline but not eliminated.

## 6. Baseline comparison

**Not yet valid — no reviewed labels exist.** `scripts/evaluate_extractor.py` refuses to
report a comparison until `review_status` ∈ {approved, corrected} (verified: exits 2).
Provisional pilot signal only: baseline F1 0.140 vs TF-IDF F1 0.333 (+0.19 margin).
The absolute 0.50 bar remains distant on provisional data — the eval plan already
provides for revising the absolute threshold after reviewed pilot numbers.

## 7. Known limitations

1. Zero reviewed labels: no claim test, gates provisional, F1 numbers provisional.
2. True paraphrase is unsolved by TF-IDF (needs embeddings or learned models).
3. Char n-grams trade recall for spurious subword false positives.
4. Templated skill sets (~41 distinct) cap per-occupation discrimination (intrinsic MRR 0.29).
5. English-only; no handling of code-mixed (Hinglish) input.
6. Score scale is corpus-dependent; gates must be re-tuned if data changes.
7. char/maxpool build ≈ 60 s (acceptable one-time cost; queries are milliseconds).

## 8. Embedding experiment — feasibility assessment (§6)

- **Checked:** `sentence-transformers` + `torch` not installed. Would require torch CPU
  (~190 MB) + transformers/tokenizers (~15 MB) + `all-MiniLM-L6-v2` (~90 MB) ≈ 300 MB
  download; 97 GB disk available, so storage is not the blocker. Offline inference after
  download — no API calls, no paid service.
- **Blockers:** (a) no reviewed labels exist, so the required fair comparison "on the
  same reviewed evaluation set" cannot be run today; (b) heavyweight install for an
  experiment whose evaluation is blocked anyway.
- **Decision:** deferred as future work. Concrete protocol when unblocked: encode the
  241 label-docs + query with `all-MiniLM-L6-v2`, cosine rank, compare micro-F1 vs
  TF-IDF on the locked reviewed held-out set with identical gates methodology; keep
  TF-IDF as the reproducible fallback. Do not claim superiority without that run.

## 9. Reproducibility

```bash
# environment
python3 -m venv .venv && .venv/bin/pip install pandas pytest scikit-learn joblib

# build + query (lazy singleton builds from data files; ~60 s first call for char)
.venv/bin/python -m engine.extract --text "I did the accounts in Tally" --top-k 5
.venv/bin/python -m engine.extract --text "..." --save data/models/tfidf_v0.1.0.joblib

# tests (53 tests)
.venv/bin/python -m pytest tests/ -q

# evaluation harness (refuses without reviewed labels; --diagnostics for smoke only)
.venv/bin/python scripts/evaluate_extractor.py
.venv/bin/python scripts/evaluate_extractor.py --diagnostics

# config comparison (reproduces §2a table)
.venv/bin/python scripts/compare_vectorizers.py
```

Model predictions reproduce exactly given identical `data/raw`, `data/processed`, and
`ExtractorConfig` (stable sorts, no randomness; md5 checksum in model metadata).
Rebuild the registry first if vocabulary changes: `scripts/build_registry.py`.

## 10. Next experiments

1. Human review of pilot → re-tune gates → build 100–120-description held-out set → run claim test.
2. Embedding comparison per §8 protocol.
3. Tune w_label/w_ctx and ngram ranges on reviewed dev split.
4. Review-queue recall gap: improve near-duplicate detection (embeddings or token-Jaccard < 0.5 pairs like Soil Analysis/Soil Science).
5. Occupation ranking (`match.py`) reusing the maxpool occupation similarities — direct input to Component B.
