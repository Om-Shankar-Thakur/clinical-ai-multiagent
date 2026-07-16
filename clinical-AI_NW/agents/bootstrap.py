# agents/bootstrap.py

"""
Registry bootstrap
==================
Single place where agents register themselves into an :class:`AgentRegistry`.

The executor receives a populated registry and resolves agents by name; it never
imports agent classes. Adding a new agent = adding one ``register(...)`` line
here (plus the adapter) - no executor change required.

Factories are zero-arg callables and are only invoked lazily by the registry on
first use, so an agent that a given plan does not select never constructs its
heavy dependencies (FAISS indices, embedding model, LLM client).
"""

from __future__ import annotations

from core.registry import AgentRegistry


def build_default_registry() -> AgentRegistry:
    """Return a registry populated with every built-in clinical agent."""
    from agents.adapters import (
        SymptomAgentAdapter,
        LabAgentAdapter,
        DiagnosisArbiterAdapter,
        TreatmentPlannerAdapter,
        DrugCheckerAdapter,
    )
    from agents.supervisor_agent import SupervisorAdapter

    registry = AgentRegistry()
    registry.register("symptom_agent", SymptomAgentAdapter)
    registry.register("lab_agent", LabAgentAdapter)
    registry.register("diagnosis_arbiter", DiagnosisArbiterAdapter)
    registry.register("treatment_planner", TreatmentPlannerAdapter)
    registry.register("drug_checker", DrugCheckerAdapter)
    registry.register("supervisor", SupervisorAdapter)

    return registry
