"""Transition Recommender (Component B, Phase 4).

Given a current skills profile (canonical skill IDs) and a target occupation,
returns skill gaps, an explained prioritized learning pathway, and a HEURISTIC
ranking score. The heuristic score is transparently documented and is NEVER a
probability; twelve-month feasibility is reported as unavailable (see
engine/calibration.py for why honest calibration is not feasible here).

Nothing is invented: salaries, education requirements, exams, and demand come
from the dataset. Learning suggestions are generic and explicitly labeled as
heuristic suggestions, never dataset facts.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

DEMAND_WEIGHT = {"Very High Growth": 1.0, "High Growth": 0.75,
                 "Emerging": 0.6, "Stable": 0.4}
EDU_ORDER = {"10th Pass": 0, "12th Pass": 1, "Diploma": 2, "Bachelor's": 3,
             "Master's": 4, "PhD": 5}
REQUIRED_COLUMNS = {"id", "title", "domain", "chunk_text", "required_skills",
                    "education_required", "india_salary_lpa_median",
                    "india_salary_percentiles", "india_demand_trend",
                    "india_qualifying_exams", "india_top_cities",
                    "bright_outlook", "remote_friendly"}


def _parse_json_list(raw: str):
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


class TransitionRecommender:
    def __init__(self):
        self.occupations: dict[str, dict] = {}
        self.skill_id_to_label: dict[str, str] = {}
        self.occ_skills: dict[str, list[str]] = {}
        self.domain_occs: dict[str, list[str]] = {}
        self.extractor = None  # optional SkillExtractor for context fit

    @classmethod
    def build(cls, raw_csv: str | Path, processed_dir: str | Path,
              extractor=None) -> "TransitionRecommender":
        raw_csv, processed_dir = Path(raw_csv), Path(processed_dir)
        rec = cls()
        with raw_csv.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            if missing:
                raise ValueError(
                    f"raw dataset missing required columns: {sorted(missing)}")
            rows = list(reader)
        if not rows:
            raise ValueError("raw dataset is empty")
        with (processed_dir / "skill_registry.csv").open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rec.skill_id_to_label[r["skill_id"]] = r["label"]
        label_to_id = {v: k for k, v in rec.skill_id_to_label.items()}
        for r in rows:
            occ_id = r["id"].strip()
            skill_ids = []
            for raw in json.loads(r["required_skills"]):
                label = re.sub(r"\s+", " ", raw.strip())
                if label not in label_to_id:
                    raise ValueError(f"skill {label!r} not in registry")
                skill_ids.append(label_to_id[label])
            rec.occ_skills[occ_id] = skill_ids
            rec.domain_occs.setdefault(r["domain"].strip(), []).append(occ_id)
            rec.occupations[occ_id] = {
                "id": occ_id,
                "title": r["title"].strip(),
                "domain": r["domain"].strip(),
                "education_required": r["education_required"].strip(),
                "salary_lpa_median": int(r["india_salary_lpa_median"]),
                "salary_percentiles": json.loads(r["india_salary_percentiles"]),
                "demand_trend": r["india_demand_trend"].strip(),
                "qualifying_exams": _parse_json_list(r["india_qualifying_exams"]),
                "top_cities": _parse_json_list(r["india_top_cities"]),
                "bright_outlook": r["bright_outlook"].strip().lower() == "true",
                "remote_friendly": r["remote_friendly"].strip().lower() == "true",
                "chunk_text": (r["chunk_text"] or "").strip(),
            }
        rec.extractor = extractor
        return rec

    # ------------------------------------------------------------------ core
    def recommend(self, profile_skill_ids: list[str], target_occupation_id: str,
                  profile_education: str | None = None, top_k_pathway: int = 10) -> dict:
        if target_occupation_id not in self.occupations:
            raise ValueError(
                f"unknown target occupation: {target_occupation_id!r} "
                f"(not in dataset)")
        if not isinstance(profile_skill_ids, (list, tuple)):
            raise TypeError("profile_skill_ids must be a list of skill IDs")
        warnings: list[str] = []
        seen, profile, unknown = set(), [], []
        for sid in profile_skill_ids:
            if sid not in self.skill_id_to_label:
                if sid not in seen:
                    unknown.append(sid)
                continue
            if sid not in seen:
                seen.add(sid)
                profile.append(sid)
        if unknown:
            warnings.append(f"unknown skill IDs ignored: {unknown}")
        if len(profile_skill_ids) != len(profile) + len(unknown):
            warnings.append("duplicate skill IDs in profile were deduplicated")

        occ = self.occupations[target_occupation_id]
        required = self.occ_skills[target_occupation_id]
        matched = [s for s in required if s in profile]
        missing = [s for s in required if s not in profile]
        dice = (2 * len(matched) / (len(profile) + len(required))) if (profile or required) else 0.0

        # education fit (only when the caller provides it)
        education_fit = None
        if profile_education is not None:
            if profile_education not in EDU_ORDER:
                raise ValueError(f"unknown education level: {profile_education!r}")
            req = EDU_ORDER.get(occ["education_required"], 0)
            got = EDU_ORDER[profile_education]
            education_fit = 1.0 if got >= req else got / max(req, 1)

        # context fit via extractor (not skill overlap alone)
        context_fit = None
        if self.extractor is not None:
            from sklearn.metrics.pairwise import cosine_similarity
            from engine.extract import _clean
            query_text = _clean(" ".join(self.skill_id_to_label[s] for s in profile))
            q = self.extractor.vectorizer.transform([query_text or " "])
            idx = self.extractor.occ_ids.index(target_occupation_id)
            context_fit = float(cosine_similarity(q, self.extractor._occ_matrix[idx])[0][0])
        else:
            warnings.append("context fit unavailable (no extractor); "
                            "ranking uses skill overlap and education only")

        # heuristic score: transparent weighted sum, renormalized over available parts
        parts = {"skill_overlap": dice}
        if education_fit is not None:
            parts["education_fit"] = education_fit
        if context_fit is not None:
            parts["context_fit"] = context_fit
        weights = {"skill_overlap": 0.55, "education_fit": 0.25, "context_fit": 0.20}
        wsum = sum(weights[k] for k in parts)
        heuristic = sum(parts[k] * weights[k] for k in parts) / wsum if wsum else 0.0

        # data-quality warnings
        twins = sum(1 for oid, sk in self.occ_skills.items()
                    if oid != target_occupation_id and set(sk) == set(required))
        if twins:
            warnings.append(
                f"skill overlap alone cannot distinguish {occ['title']} from "
                f"{twins} other occupation(s) with an identical skill set; "
                f"context fit is included in the ranking where available")

        pathway = self._pathway(missing, occ, top_k_pathway)
        return {
            "target_occupation": {k: occ[k] for k in
                                  ("id", "title", "domain", "education_required",
                                   "salary_lpa_median", "salary_percentiles",
                                   "demand_trend", "qualifying_exams",
                                   "top_cities", "bright_outlook", "remote_friendly")},
            "profile": {"n_skills": len(profile), "unknown_skill_ids": unknown},
            "matched_skills": [{"skill_id": s, "label": self.skill_id_to_label[s]}
                               for s in matched],
            "missing_skills": [{"skill_id": s, "label": self.skill_id_to_label[s]}
                               for s in missing],
            "skill_overlap": {"dice": round(dice, 4), "n_matched": len(matched),
                              "n_required": len(required), "n_profile": len(profile)},
            "explanation": self._explain(occ, len(matched), len(required), len(profile),
                                        dice, education_fit, context_fit),
            "pathway": pathway,
            "education": {"required": occ["education_required"],
                          "qualifying_exams": occ["qualifying_exams"],
                          "profile_education": profile_education,
                          "note": "from dataset; profile education only used if provided"},
            "heuristic_rank_score": round(heuristic, 4),
            "score_breakdown": {k: round(v, 4) for k, v in parts.items()},
            "score_note": ("heuristic ranking score for ordering suggestions; "
                           "NOT a probability and NOT calibrated"),
            "twelve_month_feasibility": {
                "available": False,
                "reason": ("no observed transition-outcome labels exist; a calibrated "
                           "12-month probability cannot be honestly estimated"),
                "what_is_needed": ("labeled outcomes of real career transitions "
                                   "(achieved within 12 months: yes/no) to fit and "
                                   "validate a calibrator; see engine/calibration.py"),
            },
            "warnings": warnings,
        }

    def _pathway(self, missing: list[str], occ: dict, top_k: int) -> list[dict]:
        domain_occs = self.domain_occs[occ["domain"]]
        demand_w = DEMAND_WEIGHT.get(occ["demand_trend"], 0.5)
        items = []
        for sid in missing:
            in_domain = sum(1 for oid in domain_occs if sid in self.occ_skills[oid])
            transferability = in_domain / len(domain_occs)
            global_count = sum(1 for sk in self.occ_skills.values() if sid in sk)
            learnability = 1.0 - global_count / len(self.occ_skills)
            priority = round(0.5 * transferability + 0.3 * demand_w + 0.2 * learnability, 4)
            steps = []
            if occ["qualifying_exams"]:
                steps.append({"text": "Qualifying exams for this occupation include: "
                                      + ", ".join(occ["qualifying_exams"]),
                              "source": "dataset"})
            steps.append({"text": "Build demonstrable evidence: small projects or "
                                  "volunteer work using this skill, documented publicly",
                          "source": "heuristic_suggestion"})
            items.append({
                "skill_id": sid,
                "label": self.skill_id_to_label[sid],
                "priority_score": priority,
                "transferability": round(transferability, 4),
                "demand_weight": demand_w,
                "why": (f"Required by {occ['title']}; also required by "
                        f"{in_domain - 1} other {occ['domain']} occupation(s)"),
                "next_steps": steps,
            })
        items.sort(key=lambda x: -x["priority_score"])
        return items[:top_k]

    @staticmethod
    def _explain(occ, n_matched, n_required, n_profile, dice, education_fit, context_fit) -> str:
        parts = [
            f"Your profile lists {n_profile} skill(s); {occ['title']} requires {n_required}.",
            f"{n_matched} overlap (Dice {dice:.2f}).",
        ]
        if education_fit is not None:
            parts.append(f"Education fit {education_fit:.2f} "
                         f"(required: {occ['education_required']}).")
        if context_fit is not None:
            parts.append(f"Occupational-context fit {context_fit:.2f} "
                         f"(profile text vs role description).")
        parts.append("The pathway prioritizes missing skills by transferability "
                     "within the role's domain, labour demand, and learnability.")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# module-level convenience (lazy singleton, no extractor -> context unavailable)
# ---------------------------------------------------------------------------

_RECOMMENDER: TransitionRecommender | None = None


def _default_paths():
    root = Path(__file__).resolve().parent.parent
    return root / "data" / "raw" / "indian_skills_dataset.csv", root / "data" / "processed"


def get_recommender(rebuild: bool = False) -> TransitionRecommender:
    global _RECOMMENDER
    if _RECOMMENDER is None or rebuild:
        raw_csv, processed = _default_paths()
        _RECOMMENDER = TransitionRecommender.build(raw_csv, processed)
    return _RECOMMENDER


def recommend(profile_skill_ids: list[str], target_occupation_id: str,
              profile_education: str | None = None) -> dict:
    return get_recommender().recommend(profile_skill_ids, target_occupation_id,
                                       profile_education)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Transition Recommender.")
    ap.add_argument("--skills", required=True, help="comma-separated skill IDs")
    ap.add_argument("--target", required=True, help="target occupation ID")
    ap.add_argument("--education", default=None)
    args = ap.parse_args()
    print(json.dumps(recommend(args.skills.split(","), args.target, args.education),
                     indent=2, ensure_ascii=False))
