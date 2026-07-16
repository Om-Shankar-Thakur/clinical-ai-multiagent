"""
core.memory
===========
Lightweight, in-memory shared context for a single clinical run.

Injected into the planner (to decide which agents to run) and the executor
(so agents read their inputs and publish their outputs through one object
instead of long positional argument chains).

This is intentionally NOT persistent. The interface is designed so a persistent
backend (Redis, a DB, a vector memory) can be dropped in later without touching
callers - only this class would change.
"""

from __future__ import annotations

from typing import Any

from core.contracts import AgentResult, TraceRecord


class ClinicalMemory:
    """In-memory working store for one orchestrator run."""

    def __init__(self) -> None:
        # Immutable-ish inputs for this run (symptoms, labs, meds, complaint).
        self.patient_context: dict[str, Any] = {}
        # agent_name -> AgentResult produced this run.
        self.agent_results: dict[str, AgentResult] = {}
        # Chronological telemetry (also mirrored into ExecutionTrace).
        self.execution_history: list[TraceRecord] = []
        # Every diagnosis object the arbiter/agents have asserted.
        self.diagnosis_history: list[dict[str, Any]] = []
        # Every plan the planner produced (usually one, but re-planning is possible).
        self.planner_decisions: list[dict[str, Any]] = []

    # ---------------------------------------------------------------- #
    #  Patient context
    # ---------------------------------------------------------------- #
    def set_patient_context(self, **context: Any) -> None:
        self.patient_context.update(context)

    def get_patient_context(self) -> dict[str, Any]:
        return dict(self.patient_context)

    # ---------------------------------------------------------------- #
    #  Agent outputs
    # ---------------------------------------------------------------- #
    def record_agent_result(self, result: AgentResult) -> None:
        self.agent_results[result.agent] = result

    def get_result(self, agent_name: str) -> AgentResult | None:
        return self.agent_results.get(agent_name)

    def get_output(self, agent_name: str, default: Any = None) -> Any:
        """Convenience: the ``output`` dict of an agent, or ``default``."""
        result = self.agent_results.get(agent_name)
        return result.output if result is not None else default

    def has_output(self, agent_name: str) -> bool:
        r = self.agent_results.get(agent_name)
        return r is not None and r.status == "success"

    def confidence_of(self, agent_name: str) -> float | None:
        r = self.agent_results.get(agent_name)
        return r.confidence if r is not None else None

    # ---------------------------------------------------------------- #
    #  Histories
    # ---------------------------------------------------------------- #
    def record_trace(self, record: TraceRecord) -> None:
        self.execution_history.append(record)

    def record_diagnosis(self, diagnosis: dict[str, Any]) -> None:
        self.diagnosis_history.append(diagnosis)

    def record_planner_decision(self, decision: dict[str, Any]) -> None:
        self.planner_decisions.append(decision)

    # ---------------------------------------------------------------- #
    #  Snapshot (debugging / observability)
    # ---------------------------------------------------------------- #
    def snapshot(self) -> dict[str, Any]:
        return {
            "patient_context": self.patient_context,
            "agent_confidences": {
                name: r.confidence for name, r in self.agent_results.items()
            },
            "diagnosis_history": self.diagnosis_history,
            "planner_decisions": self.planner_decisions,
        }
