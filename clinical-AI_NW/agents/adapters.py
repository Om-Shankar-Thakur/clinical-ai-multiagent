# agents/adapters.py

"""
Agent adapters
==============
Thin :class:`~core.base_agent.BaseAgent` wrappers around the existing domain
agents. Adapters are the ONLY place that knows each agent's real method
signature; they:

- read the agent's inputs from shared :class:`~core.memory.ClinicalMemory`,
- call the underlying (unchanged) agent,
- publish a uniform :class:`~core.contracts.AgentResult` with a self-assessed
  ``confidence`` and an ``input_assessment`` (the confidence it observed in the
  upstream outputs it consumed - i.e. confidence chaining).

The underlying agents are imported and constructed lazily *inside* each adapter
so that importing this module has no heavy side effects, and so an unused agent
never loads its FAISS/model resources.

Declared ``dependencies`` are used by the executor purely to order execution
stages (topological layering); they are filtered to whatever is actually in the
plan, so e.g. the arbiter still runs when only one intake agent was selected.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from core.base_agent import BaseAgent
from core.contracts import AgentResult

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  Shared helper: parse LLM JSON tolerating markdown fences
#  (moved verbatim from ClinicalOrchestrator._safe_parse_json)
# --------------------------------------------------------------------------- #
def _safe_parse_json(text: str) -> dict:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(
            line for line in cleaned.splitlines()
            if not line.strip().startswith("```")
        )
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "raw_response": text,
            "warnings": ["Could not parse drug interaction response as JSON."],
            "severity": "unknown",
            "review_required": True,
        }


# --------------------------------------------------------------------------- #
#  Symptom analyzer
# --------------------------------------------------------------------------- #
class SymptomAgentAdapter(BaseAgent):
    name = "symptom_agent"
    dependencies: list[str] = []

    def __init__(self) -> None:
        from agents.symptom_analyzer import SymptomAnalyzerAgent
        self._agent = SymptomAnalyzerAgent()

    def execute(self, memory) -> AgentResult:
        ctx = memory.get_patient_context()
        chief_complaint = ctx.get("chief_complaint", "")
        symptoms = ctx.get("symptoms", []) or []
        try:
            output = self._agent.analyze(chief_complaint, symptoms)
            differential = output.get("differential_diagnosis", [])
            confidence = float(differential[0]["score"]) if differential else 0.0
            return AgentResult(
                agent=self.name, output=output, confidence=round(confidence, 3)
            )
        except Exception as e:  # noqa: BLE001 - convert to safe result
            logger.error("symptom_agent failed: %s", e)
            return AgentResult(
                agent=self.name,
                output={"chief_complaint": chief_complaint, "differential_diagnosis": []},
                confidence=0.0,
                status="error",
                error=str(e),
            )


# --------------------------------------------------------------------------- #
#  Lab interpreter
# --------------------------------------------------------------------------- #
class LabAgentAdapter(BaseAgent):
    name = "lab_agent"
    dependencies: list[str] = []

    def __init__(self) -> None:
        from agents.lab_interpreter_agent import LabInterpreterAgent
        self._agent = LabInterpreterAgent()

    def execute(self, memory) -> AgentResult:
        ctx = memory.get_patient_context()
        lab_results = ctx.get("lab_results", {}) or {}
        try:
            output = self._agent.analyze(lab_results)
            hypotheses = output.get("lab_hypotheses", [])
            if hypotheses:
                confidence = float(hypotheses[0]["score"])
            elif output.get("lab_signals"):
                confidence = 0.3
            else:
                confidence = 0.0
            return AgentResult(
                agent=self.name, output=output, confidence=round(confidence, 3)
            )
        except Exception as e:  # noqa: BLE001
            logger.error("lab_agent failed: %s", e)
            return AgentResult(
                agent=self.name,
                output={"lab_hypotheses": [], "critical_flags": [], "lab_signals": []},
                confidence=0.0,
                status="error",
                error=str(e),
            )


# --------------------------------------------------------------------------- #
#  Diagnosis arbiter (medical reasoning moved out of the orchestrator)
# --------------------------------------------------------------------------- #
class DiagnosisArbiterAdapter(BaseAgent):
    name = "diagnosis_arbiter"
    # Ordering only: run after whichever intake agents were selected.
    dependencies = ["symptom_agent", "lab_agent"]

    def __init__(self) -> None:
        from agents.diagnosis_arbiter_agent import DiagnosisArbiterAgent
        self._agent = DiagnosisArbiterAgent()

    def execute(self, memory) -> AgentResult:
        symptom_output = memory.get_output("symptom_agent", {}) or {}
        lab_output = memory.get_output("lab_agent", {}) or {}

        diagnosis_output, dissenting = self._agent.arbitrate(symptom_output, lab_output)

        # Persist the diagnosis into memory's diagnosis history for governance.
        memory.record_diagnosis(diagnosis_output["final"])

        confidence = float(diagnosis_output["final"].get("confidence", 0.0) or 0.0)
        return AgentResult(
            agent=self.name,
            output={**diagnosis_output, "dissenting_opinions": dissenting},
            confidence=round(confidence, 3),
            input_assessment={
                "symptom_agent": memory.confidence_of("symptom_agent"),
                "lab_agent": memory.confidence_of("lab_agent"),
            },
        )


# --------------------------------------------------------------------------- #
#  Treatment planner
# --------------------------------------------------------------------------- #
class TreatmentPlannerAdapter(BaseAgent):
    name = "treatment_planner"
    dependencies = ["diagnosis_arbiter"]

    def __init__(self) -> None:
        from agents.treatment_planner_agent import TreatmentPlannerAgent
        self._agent = TreatmentPlannerAgent()

    def execute(self, memory) -> AgentResult:
        diagnosis_output = memory.get_output("diagnosis_arbiter", {}) or {}
        lab_output = memory.get_output("lab_agent", {}) or {}
        try:
            output = self._agent.analyze(
                diagnosis_output=diagnosis_output,
                lab_output=lab_output,
                drug_safety_output=None,  # drug check happens AFTER (preserved order)
            )
            status = output.get("recommendation_status")
            if status == "draft_for_clinician_review":
                confidence = float(output.get("diagnosis_confidence", 0.5) or 0.5)
            elif status == "insufficient_confidence":
                confidence = float(output.get("diagnosis_confidence", 0.0) or 0.0)
            else:  # generation_failed or unknown
                confidence = 0.1
            return AgentResult(
                agent=self.name,
                output=output,
                confidence=round(confidence, 3),
                input_assessment={
                    "diagnosis_arbiter": memory.confidence_of("diagnosis_arbiter")
                },
            )
        except Exception as e:  # noqa: BLE001
            logger.error("treatment_planner failed: %s", e)
            return AgentResult(
                agent=self.name,
                output={
                    "recommendation_status": "generation_failed",
                    "management_options": [],
                    "uncertainty_notes": [
                        "Treatment option generation failed. Manual clinician review required."
                    ],
                },
                confidence=0.0,
                status="error",
                error=str(e),
            )


# --------------------------------------------------------------------------- #
#  Drug interaction checker
# --------------------------------------------------------------------------- #
class DrugCheckerAdapter(BaseAgent):
    name = "drug_checker"
    dependencies = ["treatment_planner"]

    def __init__(self) -> None:
        from agents.drug_interaction_checker_agent import DrugInteractionCheckerAgent
        self._agent = DrugInteractionCheckerAgent()

    def execute(self, memory) -> AgentResult:
        ctx = memory.get_patient_context()
        meds = ctx.get("current_medications", []) or []

        # Preserve prior behaviour: skip the LLM call when no medications given.
        if not meds:
            return AgentResult(
                agent=self.name,
                output={
                    "warnings": [],
                    "severity": "low",
                    "review_required": False,
                    "note": "No current medications provided; interaction check skipped.",
                },
                confidence=0.9,
                status="skipped",
            )

        diagnosis_output = memory.get_output("diagnosis_arbiter", {}) or {}
        primary_dx = diagnosis_output.get("final", {}).get("diagnosis")
        treatment_plan = memory.get_output("treatment_planner", {}) or {}

        try:
            raw = self._agent.check(
                diagnosis=primary_dx,
                current_medications=meds,
                proposed_plan=treatment_plan,
            )
            parsed = _safe_parse_json(raw)
            confidence = self._confidence_from_parsed(parsed)
            return AgentResult(
                agent=self.name,
                output=parsed,
                confidence=confidence,
                input_assessment={
                    "treatment_planner": memory.confidence_of("treatment_planner")
                },
            )
        except Exception as e:  # noqa: BLE001
            logger.error("drug_checker failed: %s", e)
            return AgentResult(
                agent=self.name,
                output={
                    "warnings": ["Drug interaction check encountered an error."],
                    "severity": "unknown",
                    "review_required": True,
                    "error": str(e),
                },
                confidence=0.2,
                status="error",
                error=str(e),
            )

    @staticmethod
    def _confidence_from_parsed(parsed: dict[str, Any]) -> float:
        if parsed.get("severity") == "unknown":
            return 0.2
        if not parsed.get("review_required", True):
            return 0.9
        return {"high": 0.4, "medium": 0.55, "low": 0.7}.get(
            parsed.get("severity", "low"), 0.6
        )
