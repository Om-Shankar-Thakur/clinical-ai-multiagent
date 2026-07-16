# agents/diagnosis_arbiter_agent.py

"""
DiagnosisArbiterAgent
=====================
Merges the Symptom Analyzer and Lab Interpreter outputs into a single
authoritative diagnosis with confidence and dissenting opinions.

This is the medical-reasoning step that previously lived inside the
orchestrator (``_arbitrate_diagnosis`` / ``_rank_position``). It has been moved
here VERBATIM so that:

- the executor contains no medical reasoning, and
- the arbitration weights/thresholds are unit-testable in isolation.

The 0.55 / 0.45 weighting and all edge cases are preserved exactly, so the
diagnosis output is numerically identical to the previous implementation when
both intake agents ran. When only one intake agent ran, the missing side simply
contributes empty candidates (the merge already tolerates this).
"""

from __future__ import annotations

from typing import Any


class DiagnosisArbiterAgent:
    """Pure, dependency-free arbitration logic (no LLM, no I/O)."""

    def arbitrate(
        self, symptom_output: dict, lab_output: dict
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """
        Return ``(diagnosis_output, dissenting_opinions)``.

        Strategy
        --------
        1. Score each disease by combining symptom score + lab score.
        2. Pick the top-scoring disease as primary diagnosis.
        3. Collect dissenting opinions where agents disagree on ranking.
        """
        # -- Symptom candidates --
        symptom_candidates = {}
        for entry in symptom_output.get("differential_diagnosis", []):
            disease = entry["disease"].lower()
            symptom_candidates[disease] = {
                "symptom_score": entry["score"],
                "confidence": entry["reasoning"]["confidence"],
                "matched_symptoms": entry["reasoning"]["matched_symptoms"],
                "missing_symptoms": entry["reasoning"]["missing_symptoms"],
                "description": entry.get("description", ""),
            }

        # -- Lab candidates --
        lab_candidates = {}
        for entry in lab_output.get("lab_hypotheses", []):
            disease = entry["disease"].lower()
            lab_candidates[disease] = {
                "lab_score": entry["score"],
                "lab_support": entry["lab_support"],
                "matched_lab_patterns": entry["matched_lab_patterns"],
            }

        # -- Merge --
        all_diseases = set(symptom_candidates.keys()) | set(lab_candidates.keys())

        merged = []
        for disease in all_diseases:
            sym = symptom_candidates.get(disease, {})
            lab = lab_candidates.get(disease, {})

            symptom_score = sym.get("symptom_score", 0.0)
            lab_score = lab.get("lab_score", 0.0)

            # Weighted combination: 55 % symptoms, 45 % lab
            combined_score = 0.55 * symptom_score + 0.45 * lab_score

            merged.append({
                "disease": disease,
                "combined_score": round(combined_score, 3),
                "symptom_score": round(symptom_score, 3),
                "lab_score": round(lab_score, 3),
                "lab_support": lab.get("lab_support", "no lab data"),
                "symptom_confidence": sym.get("confidence", "none"),
                "matched_symptoms": sym.get("matched_symptoms", []),
                "missing_symptoms": sym.get("missing_symptoms", []),
                "matched_lab_patterns": lab.get("matched_lab_patterns", []),
                "description": sym.get("description", ""),
            })

        merged.sort(key=lambda x: x["combined_score"], reverse=True)

        # -- Primary diagnosis --
        if merged:
            top = merged[0]
            primary_diagnosis = top["disease"]
            primary_confidence = top["combined_score"]
            uncertainty = primary_confidence < 0.6
        else:
            primary_diagnosis = None
            primary_confidence = 0.0
            uncertainty = True

        diagnosis_output = {
            "final": {
                "diagnosis": primary_diagnosis,
                "confidence": round(primary_confidence, 3),
                "uncertainty": uncertainty,
            },
            "ranked_candidates": merged[:5],
        }

        # -- Dissenting opinions --
        dissenting = []
        if len(merged) >= 2:
            for alt in merged[1:4]:                    # top 3 alternatives
                symptom_rank = self._rank_position(merged, alt["disease"], "symptom_score")
                lab_rank = self._rank_position(merged, alt["disease"], "lab_score")

                if abs(symptom_rank - lab_rank) >= 2:
                    dissenting.append({
                        "disease": alt["disease"],
                        "symptom_rank": symptom_rank + 1,
                        "lab_rank": lab_rank + 1,
                        "note": (
                            f"Symptom analysis ranks this #{symptom_rank + 1} "
                            f"but lab evidence ranks it #{lab_rank + 1}."
                        ),
                    })

        return diagnosis_output, dissenting

    @staticmethod
    def _rank_position(merged_list, disease, score_key):
        """Return the rank (0-based) of *disease* when sorted by *score_key*."""
        ordered = sorted(merged_list, key=lambda x: x[score_key], reverse=True)
        for i, entry in enumerate(ordered):
            if entry["disease"] == disease:
                return i
        return len(ordered)
