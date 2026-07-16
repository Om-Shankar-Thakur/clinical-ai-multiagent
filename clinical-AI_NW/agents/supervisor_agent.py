# agents/supervisor_agent.py

"""
SupervisorAgent
===============
Governance layer that runs LAST, after every other agent. It does NOT perform
medical reasoning or change any diagnosis / plan - it *validates* the assembled
result and produces an approval verdict for the supervising clinician.

Checks
------
1. diagnosis consistency   - a primary diagnosis exists and is present in the
                             ranked candidates; treatment's diagnosis matches
                             the arbitrated diagnosis.
2. confidence adequacy     - aggregate confidence meets a review threshold.
3. conflicting outputs     - dissenting opinions between symptom and lab ranking.
4. hallucination heuristic - treatment references a diagnosis the arbiter did
                             not produce.
5. treatment plan present  - treatment ran and either produced options or a
                             status explaining their absence.
6. drug results present    - when medications were supplied, an interaction
                             result exists.

Output
------
{
  "overall_confidence": float,
  "warnings": [str, ...],
  "recommendation": str,
  "approval_status": "approved" | "approved_with_warnings" | "rejected",
  "checks": { "<check>": bool, ... }
}
"""

from __future__ import annotations

import logging
from typing import Any

from core.base_agent import BaseAgent
from core.contracts import AgentResult

logger = logging.getLogger(__name__)

CONFIDENCE_REVIEW_THRESHOLD = 0.5

# Weighting used to aggregate per-agent confidence into an overall score.
_CONFIDENCE_WEIGHTS = {
    "diagnosis_arbiter": 0.5,
    "treatment_planner": 0.3,
    "drug_checker": 0.2,
}


class SupervisorAgent:
    """Pure validation logic over an assembled clinical context (no I/O)."""

    def review(self, ctx: dict[str, Any]) -> dict[str, Any]:
        diagnosis = ctx.get("diagnosis") or {}
        ranked = ctx.get("ranked_candidates") or []
        dissenting = ctx.get("dissenting_opinions") or []
        treatment = ctx.get("treatment") or {}
        drug = ctx.get("drug") or {}
        medications = ctx.get("current_medications") or []
        confidences = ctx.get("agent_confidences") or {}

        warnings: list[str] = []
        checks: dict[str, bool] = {}

        primary_dx = diagnosis.get("diagnosis")

        # 1. diagnosis consistency ------------------------------------------
        has_diagnosis = bool(primary_dx)
        checks["diagnosis_present"] = has_diagnosis
        if not has_diagnosis:
            warnings.append("No confident primary diagnosis was established.")

        in_candidates = has_diagnosis and any(
            (c.get("disease", "").lower() == str(primary_dx).lower()) for c in ranked
        )
        checks["diagnosis_in_candidates"] = in_candidates if has_diagnosis else True
        if has_diagnosis and not in_candidates:
            warnings.append(
                "Primary diagnosis is not present in the ranked candidate list "
                "(possible inconsistency)."
            )

        # 4. hallucination heuristic ----------------------------------------
        treat_dx = treatment.get("primary_diagnosis")
        consistent_treatment_dx = (
            not treat_dx
            or not has_diagnosis
            or str(treat_dx).lower() == str(primary_dx).lower()
        )
        checks["treatment_diagnosis_consistent"] = consistent_treatment_dx
        if not consistent_treatment_dx:
            warnings.append(
                f"Treatment plan references diagnosis '{treat_dx}' which differs "
                f"from the arbitrated diagnosis '{primary_dx}' (possible hallucination)."
            )

        # 5. treatment plan present -----------------------------------------
        treat_status = treatment.get("recommendation_status")
        has_options = bool(treatment.get("management_options"))
        treatment_ok = has_options or treat_status in {
            "insufficient_confidence",
            "generation_failed",
        }
        checks["treatment_plan_present"] = bool(treatment) and treatment_ok
        if treatment and not treatment_ok:
            warnings.append("Treatment planner returned no options and no explanatory status.")
        if treat_status == "generation_failed":
            warnings.append("Treatment option generation failed; manual review required.")
        if treat_status == "insufficient_confidence":
            warnings.append(
                "Diagnostic confidence was insufficient to produce management options."
            )

        # 6. drug interaction results present -------------------------------
        drug_needed = len(medications) > 0
        drug_present = bool(drug) and "review_required" in drug
        checks["drug_results_present"] = (not drug_needed) or drug_present
        if drug_needed and not drug_present:
            warnings.append(
                "Current medications were provided but no drug-interaction result is available."
            )
        if drug.get("review_required"):
            warnings.append("Drug-interaction review flagged issues requiring clinician attention.")

        # 3. conflicting outputs --------------------------------------------
        checks["no_agent_conflicts"] = len(dissenting) == 0
        if dissenting:
            warnings.append(
                f"{len(dissenting)} dissenting opinion(s) between symptom and lab evidence."
            )

        # 2. confidence adequacy --------------------------------------------
        overall_confidence = self._aggregate_confidence(confidences)
        if diagnosis.get("uncertainty"):
            overall_confidence = round(overall_confidence * 0.9, 3)
        checks["confidence_adequate"] = overall_confidence >= CONFIDENCE_REVIEW_THRESHOLD
        if not checks["confidence_adequate"]:
            warnings.append(
                f"Overall confidence ({overall_confidence:.2f}) is below the "
                f"review threshold ({CONFIDENCE_REVIEW_THRESHOLD})."
            )

        # Verdict ------------------------------------------------------------
        critical = (
            (has_diagnosis and not in_candidates)
            or not consistent_treatment_dx
            or (treatment and not treatment_ok)
            or (drug_needed and not drug_present)
        )
        if critical:
            approval_status = "rejected"
            recommendation = "Manual clinician review required before use."
        elif warnings:
            approval_status = "approved_with_warnings"
            recommendation = "May be presented to the clinician with the noted warnings."
        else:
            approval_status = "approved"
            recommendation = "Consistent decision-support output for clinician review."

        return {
            "overall_confidence": overall_confidence,
            "warnings": warnings,
            "recommendation": recommendation,
            "approval_status": approval_status,
            "checks": checks,
        }

    @staticmethod
    def _aggregate_confidence(confidences: dict[str, float]) -> float:
        num = 0.0
        denom = 0.0
        for agent, weight in _CONFIDENCE_WEIGHTS.items():
            c = confidences.get(agent)
            if c is not None:
                num += weight * float(c)
                denom += weight
        return round(num / denom, 3) if denom else 0.0


class SupervisorAdapter(BaseAgent):
    """Executor-facing wrapper: assembles context from memory, runs review."""

    name = "supervisor"
    dependencies: list[str] = []  # forced last by the normalizer

    def __init__(self) -> None:
        self._agent = SupervisorAgent()

    def execute(self, memory) -> AgentResult:
        diagnosis_output = memory.get_output("diagnosis_arbiter", {}) or {}
        ctx = {
            "diagnosis": diagnosis_output.get("final", {}),
            "ranked_candidates": diagnosis_output.get("ranked_candidates", []),
            "dissenting_opinions": diagnosis_output.get("dissenting_opinions", []),
            "treatment": memory.get_output("treatment_planner", {}) or {},
            "drug": memory.get_output("drug_checker", {}) or {},
            "current_medications": memory.get_patient_context().get("current_medications", []),
            "agent_confidences": {
                name: r.confidence for name, r in memory.agent_results.items()
            },
        }
        review = self._agent.review(ctx)
        return AgentResult(
            agent=self.name,
            output=review,
            confidence=review.get("overall_confidence", 0.0),
        )
