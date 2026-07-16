# orchestrator.py

"""
Clinical AI Orchestrator (thin coordinator)
===========================================
The orchestrator no longer contains pipeline logic or medical reasoning. It:

1. builds per-run shared memory from the patient input,
2. asks the LLM-driven :class:`~planning.clinical_planner.ClinicalPlanner`
   which agents to run,
3. hands the plan to the :class:`~execution.clinical_executor.ClinicalExecutor`,
   which resolves agents from the shared :class:`~core.registry.AgentRegistry`,
   runs them (with intra-stage parallelism) and records a trace,
4. assembles a backward-compatible report from memory + trace.

Backward compatibility
-----------------------
``run(chief_complaint, symptoms, lab_results, current_medications)`` keeps its
exact signature, and the returned report keeps every key the previous
implementation produced. New keys (``execution_plan``, ``execution_trace``,
``supervisor_review``, ``agent_confidences``) are strictly additive, so the
FastAPI schema and the Streamlit UI continue to work unchanged.

The registry (and therefore the agents, with their FAISS indices / embedding
model / LLM client) is built once per orchestrator instance and reused across
requests; only the memory, planner binding and executor are per-run.
"""

from __future__ import annotations

import logging

from agents.bootstrap import build_default_registry
from core.memory import ClinicalMemory
from core.tracing import new_execution_id
from execution.clinical_executor import ClinicalExecutor
from planning.clinical_planner import ClinicalPlanner

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "This output is a clinical decision support aid only. "
    "It does NOT constitute a prescription or medical order. "
    "All treatment decisions must be made by a licensed clinician "
    "after independent evaluation."
)


class ClinicalOrchestrator:
    """Thin coordinator around the planner-executor architecture."""

    def __init__(self) -> None:
        # Shared, reused across requests (agents lazily built + cached).
        self.registry = build_default_registry()
        # One Gemini client for planning, reused across requests.
        from llm.gemini_client import GeminiLLM
        self._planner_llm = GeminiLLM()

    # ------------------------------------------------------------------ #
    def run(
        self,
        chief_complaint: str,
        symptoms: list[str],
        lab_results: dict,
        current_medications: list[str] | None = None,
    ) -> dict:
        current_medications = current_medications or []
        execution_id = new_execution_id()

        # 1. Per-run shared memory ------------------------------------------
        memory = ClinicalMemory()
        memory.set_patient_context(
            chief_complaint=chief_complaint,
            symptoms=symptoms,
            lab_results=lab_results,
            current_medications=current_medications,
        )

        # 2. Plan (LLM decides which agents run) ----------------------------
        planner = ClinicalPlanner(llm=self._planner_llm, memory=memory)
        plan = planner.plan(memory.get_patient_context())
        logger.info(
            "[orchestrator] execution_id=%s plan(source=%s)=%s",
            execution_id, plan.source, plan.agents,
        )

        # 3. Execute --------------------------------------------------------
        executor = ClinicalExecutor(self.registry, memory)
        trace = executor.execute(plan, execution_id=execution_id)

        # 4. Assemble backward-compatible report ----------------------------
        return self._build_final_report(memory, plan, trace)

    # ------------------------------------------------------------------ #
    def _build_final_report(self, memory: ClinicalMemory, plan, trace) -> dict:
        ctx = memory.get_patient_context()

        diagnosis_output = memory.get_output("diagnosis_arbiter", {}) or {}
        final_dx = diagnosis_output.get("final") or {
            "diagnosis": None, "confidence": 0.0, "uncertainty": True,
        }
        ranked = diagnosis_output.get("ranked_candidates", [])
        dissenting = diagnosis_output.get("dissenting_opinions", [])

        lab_output = memory.get_output("lab_agent", {}) or {}
        treatment_output = memory.get_output("treatment_planner", {}) or {}
        drug_output = memory.get_output("drug_checker")
        supervisor_output = memory.get_output("supervisor", {}) or {}

        if drug_output is None:
            # drug_checker was not selected (typically: no medications given)
            drug_output = {
                "warnings": [],
                "severity": "low",
                "review_required": False,
                "note": "Drug interaction check not performed for this patient.",
            }

        return {
            # ---- existing schema (unchanged keys) ----
            "patient_input": {
                "chief_complaint": ctx.get("chief_complaint"),
                "symptoms": ctx.get("symptoms", []),
                "lab_results": ctx.get("lab_results", {}),
                "current_medications": ctx.get("current_medications", []),
            },
            "diagnosis": final_dx,
            "ranked_candidates": ranked,
            "lab_signals": lab_output.get("lab_signals", []),
            "critical_flags": lab_output.get("critical_flags", []),
            "treatment_plan": {
                "status": treatment_output.get("recommendation_status"),
                "management_options": treatment_output.get("management_options", []),
                "uncertainty_notes": treatment_output.get("uncertainty_notes", []),
            },
            "drug_interaction_check": drug_output,
            "dissenting_opinions": dissenting,
            "clinician_action_required": True,
            "disclaimer": DISCLAIMER,

            # ---- additive: planner-executor observability ----
            "execution_plan": plan.to_dict(),
            "execution_trace": trace.to_dict(),
            "supervisor_review": supervisor_output,
            "agent_confidences": {
                name: r.confidence for name, r in memory.agent_results.items()
            },
        }
