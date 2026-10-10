# Phase 1 — Dataset Audit

**Project:** THE UNMAPPED (MEDHA Hackathon, PS-02 — Social Upliftment)
**Date:** 2026-10-10
**Auditor method:** direct download + pandas inspection (no fabricated statistics)

---

## 1. Access summary

| Dataset | Source | Access result |
|---|---|---|
| Indian Skills Dataset (official, organizer-provided) | Google Drive `1QYuK-6CRPtEC9PUbhjIGcWz-VHiDC5Md` | **Downloaded successfully** via direct `uc?export=download` link on 2026-10-10. Saved to `data/raw/indian_skills_dataset.csv`. |
| O*NET 31.0 database | onetcenter.org/database.html | **Reachable, not downloaded in Phase 1.** Download bundles confirmed available (Excel, JSON-LD, MySQL, MSSQL, Oracle). Optional Phase 2 extension via the `onet_soc_code` crosswalk already present in the Indian dataset. |
| ESCO | esco.ec.europa.eu/en/use-esco/download | **Reachable (HTTP 200), not downloaded in Phase 1.** Optional extension; no ESCO identifiers exist in the Indian dataset, so any ESCO join would require a manual crosswalk. |

O*NET/ESCO were deliberately not downloaded: Phase 1 scope is audit + planning, and the Indian dataset alone covers Components A and B.

---

## 2. File manifest — Indian Skills Dataset

- **Filename:** `indian_skills_dataset.csv`
- **Format:** CSV, UTF-8 with BOM
- **Size:** 2,267,681 bytes
- **MD5:** `65847ce119bf99b20a3761bb2ce87ea2`
- **Rows:** 820 (one per occupation/role profile)
- **Columns:** 21

### 2.1 Columns and types

| Column | dtype | Meaning |
|---|---|---|
| `id` | str | Occupation key, e.g. `soc_11-1011.00` |
| `title` | str | Indian-context occupation title (820 unique) |
| `onet_soc_code` | str | O*NET SOC code, e.g. `11-1011.00` |
| `domain` | str | Role family / sector label |
| `description` | str | Short description (21 rows missing) |
| `chunk_text` | str | ~1.8k-char Indian-context prose per occupation (retrieval-ready) |
| `required_skills` | str (JSON array) | Exactly 10 skill-name strings per occupation |
| `education_required` | str | Categorical: Bachelor's / Diploma / Master's / 12th Pass / 10th Pass / PhD |
| `stream_required` | str (JSON array) | e.g. `["Any"]` |
| `segment_relevance` | str (JSON array) | Audience segments, e.g. `["UG", "PostGrad"]`, `["11-12", "UG"]` |
| `india_salary_lpa_median` | int | Median salary, LPA |
| `india_salary_percentiles` | str (JSON obj) | `{p25, p50, p75, p90}` |
| `india_demand_trend` | str | Emerging / High Growth / Stable / Very High Growth |
| `india_top_cities` | str (JSON array) | Hiring cities |
| `india_top_recruiters` | str (JSON array) | Example employers |
| `india_qualifying_exams` | str (JSON array) | e.g. `["UPSC Civil Services Examination"]` |
| `bright_outlook` | bool | Growth flag (497 true / 323 false) |
| `remote_friendly` | bool | 344 true / 476 false |
| `riasec_primary` | str | Holland code letter |
| `riasec_scores` | str (JSON obj) | `{R, I, A, S, E, C}` scores |
| `source` | str | `onet_enriched` (816) / `india_custom` (4) |

### 2.2 Missing values and duplicates

- **Missing:** only `description` at 2.56% (21/820 rows). Every other column: 0% missing.
- **Duplicates:** 0 fully-duplicate rows; 0 duplicate `id` values.

### 2.3 Salary and demand fields (dashboard-relevant)

- `india_salary_lpa_median`: range 3–35 LPA, mean 9.5, median 7. `p50` equals the median column on all 820 rows (internally consistent).
- Demand trend: High Growth 381, Stable 334, Emerging 67, Very High Growth 38.
- Top domains by size: Healthcare & Medical (114), Installation/Maintenance/Repair (72), Management & Leadership (63), Science & Research (59), Architecture & Engineering (57), Education & Training (56).

---

## 3. Taxonomy analysis — the critical findings

### 3.1 Skill vocabulary

- **241 unique skill strings** across 8,200 skill mentions (10 per occupation, no exceptions).
- Skills are **plain-text names, not taxonomy identifiers.** There are no O*NET skill element IDs, no ESCO concept URIs, no numeric skill codes. "Taxonomy-grounded" therefore means grounded in *this dataset's* 241-skill controlled vocabulary (with an optional O*NET crosswalk at the *occupation* level via `onet_soc_code`), not in an external skill ID system.
- Generic skills dominate: `Communication` appears in 395/820 occupations (48%), `Problem Solving` in 234, `Research` in 223. 78 skills are singletons (appear once).

### 3.2 ⚠️ Skill sets are heavily templated (major limitation)

- Only **~41 distinct skill sets** exist across 820 occupations.
- **799 of 820 occupations share an identical 10-skill set with at least one other occupation**, in just 20 groups. Largest groups: 96, 68, 66, 65, 59 occupations.
- Near-duplicate labels coexist in the vocabulary (`Communication` vs `Business Communication`; `Collaboration` vs `Team Collaboration`).

**Implication:** `required_skills` alone cannot discriminate between occupations within a domain (e.g., dozens of healthcare roles share one identical skill list). Any occupation-matching or gap analysis that relies only on skill overlap will produce ties and weak rankings. The matching strategy must combine skill overlap with `chunk_text` similarity, education/segment filters, and RIASEC — this is designed into the architecture (see `phase-1-architecture.md`).

### 3.3 Occupation identifiers

- All 820 `onet_soc_code` values match the SOC pattern `XX-XXXX.XX`; 802 unique SOC codes for 820 rows (18 Indian titles share a SOC code with another title, e.g. multiple civil-service titles under `11-1011.00`).
- 4 `india_custom` rows (Agriculture Officer, Civil Judge, Yoga/Naturopathy Practitioner, Ayurvedic/Homeopathic Doctor) extend O*NET with India-specific roles. Their SOC codes are mapped to the nearest O*NET parent (e.g. `19-1013.00`).

### 3.4 Domain taxonomy is inconsistent (minor limitation)

- 41 distinct `domain` values with overlapping variants: `Healthcare & Medical` vs `Holistic Health & Wellness` vs `Traditional Medicine & Healthcare` vs `Healthcare Support`; `Business & Finance` vs `Finance & Accounting` vs `Corporate Finance & Cost Accounting`; several single-occupation domains (`Nuclear Energy Research`, `Maritime Transport & Shipping`, `Space Research & Aerospace Engineering`).
- Dashboard aggregations should roll up to a cleaned domain mapping (documented in preprocessing), not raw values.

### 3.5 Text fields

- `chunk_text`: 1,584–2,258 chars (mean 1,799), Indian-context prose per occupation. Usable as the retrieval/matching corpus for Component A. No missing values.
- `description`: present for 799/820 rows; short. Supplementary only.

---

## 4. Fitness for each component

### Component A — Skills Signal Engine: ✅ SUPPORTED
- The 241-skill vocabulary + 820 occupation `chunk_text`s give a complete closed-world matching target: free text → skill candidates → occupation profiles.
- **Gap:** the dataset contains **zero informal-experience → skill labeled pairs**. There is no supervised training/evaluation data for extraction. The evaluation plan therefore requires a team-labeled pilot set (see `phase-1-evaluation-plan.md`).

### Component B — Transition Recommender: ✅ SUPPORTED (with calibration caveat)
- Skill-gap computation is directly supported: current profile (241-skill space) vs target occupation's `required_skills`.
- Retraining pathway inputs exist: `india_qualifying_exams`, `education_required`, `segment_relevance`.
- **Caveat:** the dataset contains **zero observed career-transition outcomes**. No dataset field records whether a real person achieved a transition in 12 months. A "calibrated probability" must therefore be calibrated against team-labeled proxy outcomes under a documented rubric — and the UI must label it as such, never as an observed labour-market statistic. (See evaluation plan §4.)

### Component C — Aggregate Signals Dashboard: ⚠️ PARTIALLY SUPPORTED (optional, later)
Genuine pre-packaged signals available:
1. **Wage signal:** median + p25/p50/p75/p90 salary by domain and occupation.
2. **Demand signal:** `india_demand_trend` + `bright_outlook` by domain (employment-growth proxy).

Not available — do not fabricate:
- **Automation exposure by occupation:** no such field exists.
- **Time series:** salary/demand are a single snapshot, not trends over time. "Wage trends" can only be shown as cross-sectional distributions, not trajectories, unless organizers supply time-series data.

---

## 5. Limitations register

| # | Limitation | Affects | Mitigation |
|---|---|---|---|
| L1 | Skills are text labels, not taxonomy IDs | A, B | Build canonical skill registry with stable IDs (`SKL-001…`) in preprocessing; optional O*NET skill crosswalk via SOC in later phase |
| L2 | Skill sets templated (~41 distinct for 820 occupations) | A, B | Multi-signal matching (skills + chunk_text + education + RIASEC); document tie-breaking |
| L3 | No informal-text → skill labeled pairs | A eval | Team-labeled pilot/held-out set (stratified by domain) |
| L4 | No observed transition outcomes | B calibration | Rubric-labeled proxy outcomes; explicit UI labeling; report ECE on held-out set |
| L5 | No automation-exposure field; no time series | C | Dashboard shows the two supported signals only; mark C optional |
| L6 | Domain labels inconsistent (41 raw values) | C, B filters | Curated domain rollup map in preprocessing |
| L7 | Generic skills dominate (`Communication` in 48%) | A ranking | TF-IDF-style downweighting of ubiquitous skills |
| L8 | `description` missing for 21 rows | A (minor) | Fall back to `chunk_text`; never surface nulls |

---

## 6. What still needs to be provided

- **Nothing is blocking Phase 2.** The Indian dataset is sufficient for Components A and B.
- For Component C beyond the two supported signals: time-series wage/demand data or an automation-exposure table — only if organizers supply it; otherwise C ships with the two genuine signals or is deferred.
- O*NET 31.0 / ESCO downloads remain optional enrichments, not requirements.
