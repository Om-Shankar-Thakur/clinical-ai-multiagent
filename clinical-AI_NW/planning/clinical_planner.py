# planning/clinical_planner.py

"""
ClinicalPlanner
===============
The planner is an LLM (Gemini). Given the available patient data it produces a
structured :class:`~core.contracts.ExecutionPlan` deciding WHICH agents run.

Design notes
------------
- The agent-selection *decision* is made by the LLM, not by hardcoded if/else
  rules. The prompt describes each agent's data prerequisites and the model
  reasons over which data is present.
- A deterministic ``_fallback_plan`` exists ONLY as a safety net for when the
  LLM returns invalid/unusable JSON (or errors). This keeps the system runnable
  offline / under LLM failure. The chosen path is recorded in
  :attr:`ExecutionPlan.source` ("llm" vs "fallback") for full transparency.
- The planner never selects the system-managed agents (``diagnosis_arbiter``,
  ``supervisor``); the executor's normaliser adds those structurally.
- Every decision is written to :class:`~core.memory.ClinicalMemory` so the run
  is auditable.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from core.contracts import ExecutionPlan
from config.prompts import CLINICAL_PLANNER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Agents the LLM is allowed to select (system-managed agents excluded).
SELECTABLE_AGENTS = {"symptom_agent", "lab_agent", "treatment_planner", "drug_checker"}


class ClinicalPlanner:
    def __init__(self, llm: Any = None, memory: Any = None) -> None:
        # Lazy default so importing this module needs no API key / SDK client.
        if llm is None:
            from llm.gemini_client import GeminiLLM
            llm = GeminiLLM()
        self.llm = llm
        self.memory = memory

    # ------------------------------------------------------------------ #
    def plan(self, patient_context: dict[str, Any]) -> ExecutionPlan:
        """Produce an ExecutionPlan for the given patient context."""
        user_prompt = self._build_user_prompt(patient_context)

        try:
            raw = self.llm.generate(CLINICAL_PLANNER_SYSTEM_PROMPT, user_prompt)
            plan = self._parse_plan(raw)
        except Exception as e:  # noqa: BLE001 - never let planning crash the run
            logger.error("Planner LLM call failed: %s", e)
            plan = None

        if plan is None:
            plan = self._fallback_plan(patient_context)

        self._record(plan)
        return plan

    # ------------------------------------------------------------------ #
    def _build_user_prompt(self, ctx: dict[str, Any]) -> str:
        symptoms = ctx.get("symptoms") or []
        chief_complaint = ctx.get("chief_complaint") or ""
        lab_results = ctx.get("lab_results") or {}
        medications = ctx.get("current_medications") or []

        availability = {
            "has_chief_complaint": bool(chief_complaint.strip()) if isinstance(chief_complaint, str) else bool(chief_complaint),
            "has_symptoms": len(symptoms) > 0,
            "has_lab_results": len(lab_results) > 0,
            "has_current_medications": len(medications) > 0,
        }

        return (
            "Decide which agents to run for this patient.\n\n"
            f"Chief complaint: {json.dumps(chief_complaint)}\n"
            f"Symptoms: {json.dumps(symptoms)}\n"
            f"Lab results: {json.dumps(lab_results)}\n"
            f"Current medications: {json.dumps(medications)}\n\n"
            f"Data availability: {json.dumps(availability)}\n\n"
            "Return the execution plan as JSON."
        )

    # ------------------------------------------------------------------ #
    def _parse_plan(self, raw: str) -> ExecutionPlan | None:
        cleaned = (raw or "").strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(
                line for line in cleaned.splitlines()
                if not line.strip().startswith("```")
            )
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Planner returned non-JSON output; using fallback.")
            return None

        if not isinstance(data, dict):
            return None

        agents = [a for a in data.get("agents", []) if a in SELECTABLE_AGENTS]
        if not agents:
            # LLM produced a structurally valid but empty/unusable selection.
            return None

        parallel = [a for a in data.get("parallel", []) if a in agents]
        reasoning = str(data.get("reasoning", "")).strip()

        # de-dup while preserving order
        agents = list(dict.fromkeys(agents))
        parallel = list(dict.fromkeys(parallel))

        return ExecutionPlan(
            agents=agents, parallel=parallel, reasoning=reasoning, source="llm"
        )

    # ------------------------------------------------------------------ #
    def _fallback_plan(self, ctx: dict[str, Any]) -> ExecutionPlan:
        """Deterministic safety net (only used when the LLM output is unusable)."""
        symptoms = ctx.get("symptoms") or []
        lab_results = ctx.get("lab_results") or {}
        medications = ctx.get("current_medications") or []
        chief_complaint = ctx.get("chief_complaint") or ""

        agents: list[str] = []
        if symptoms or (isinstance(chief_complaint, str) and chief_complaint.strip()):
            agents.append("symptom_agent")
        if lab_results:
            agents.append("lab_agent")
        # a management plan is produced whenever there is any diagnostic signal
        if agents:
            agents.append("treatment_planner")
        if medications:
            agents.append("drug_checker")

        parallel = [a for a in ("symptom_agent", "lab_agent") if a in agents]
        return ExecutionPlan(
            agents=agents,
            parallel=parallel,
            reasoning="Deterministic fallback plan derived from available patient data "
                      "(LLM planner unavailable or returned unusable output).",
            source="fallback",
        )

    # ------------------------------------------------------------------ #
    def _record(self, plan: ExecutionPlan) -> None:
        if self.memory is not None:
            self.memory.record_planner_decision(plan.to_dict())
