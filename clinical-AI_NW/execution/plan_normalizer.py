# execution/plan_normalizer.py

"""
PlanNormalizer
==============
Turns a planner-produced :class:`~core.contracts.ExecutionPlan` into an ordered
list of execution *stages* (each stage = a list of agent names that may run in
parallel).

This module performs GRAPH operations only - dependency closure and topological
layering. It makes no clinical decision about *which* agents to run; that is the
planner's (LLM's) job. The normalizer only guarantees structural integrity:

1. **Hard-prerequisite closure** - if a selected agent declares ``requires``,
   those prerequisites are pulled in (e.g. selecting ``treatment_planner`` pulls
   in ``diagnosis_arbiter``). A selected agent can never run without the
   upstream output it structurally depends on.
2. **Arbitration bridge** - if any intake agent was selected, the
   ``diagnosis_arbiter`` is included, because arbitration is the structural
   bridge from intake outputs to a diagnosis.
3. **Supervisor last** - if a ``supervisor`` agent is registered it always runs
   in a final stage (governance over the whole run).
4. **Topological layering** - agents whose (in-plan) soft ``dependencies`` are
   already satisfied are grouped into the same parallel stage.
"""

from __future__ import annotations

from core.contracts import ExecutionPlan
from core.registry import AgentRegistry

INTAKE_AGENTS = ("symptom_agent", "lab_agent")
ARBITER = "diagnosis_arbiter"
SUPERVISOR = "supervisor"


class PlanNormalizer:
    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry

    # ------------------------------------------------------------------ #
    def to_stages(self, plan: ExecutionPlan) -> list[list[str]]:
        """Return ordered parallel stages for ``plan``."""
        selected = self._select(plan)
        return self._layer(selected)

    def closure(self, plan: ExecutionPlan) -> list[str]:
        """Public helper: the effective agent set after closure (order-agnostic)."""
        return self._select(plan)

    # ------------------------------------------------------------------ #
    def _select(self, plan: ExecutionPlan) -> list[str]:
        # 1. keep only registered agents the planner chose (dedup, order-preserving)
        selected: list[str] = []
        for name in plan.agents:
            if self.registry.is_registered(name) and name not in selected:
                selected.append(name)

        # 2. hard-prerequisite closure over `requires`
        i = 0
        while i < len(selected):
            for req in self.registry.requires_of(selected[i]):
                if self.registry.is_registered(req) and req not in selected:
                    selected.append(req)
            i += 1

        # 3. arbitration bridge: intake selected => arbiter included
        if any(a in selected for a in INTAKE_AGENTS):
            if self.registry.is_registered(ARBITER) and ARBITER not in selected:
                selected.append(ARBITER)
                # arbiter may itself have requires; close again (cheap)
                for req in self.registry.requires_of(ARBITER):
                    if self.registry.is_registered(req) and req not in selected:
                        selected.append(req)

        # 4. supervisor always last (handled in layering)
        if self.registry.is_registered(SUPERVISOR) and SUPERVISOR not in selected:
            selected.append(SUPERVISOR)

        return selected

    def _layer(self, selected: list[str]) -> list[list[str]]:
        selected_set = set(selected)
        remaining = set(selected) - {SUPERVISOR}
        placed: set[str] = set()
        stages: list[list[str]] = []

        while remaining:
            ready = [
                name
                for name in remaining
                if {
                    d for d in self.registry.dependencies_of(name) if d in selected_set
                }
                <= placed
            ]
            if not ready:
                # Unsatisfiable/cyclic (shouldn't happen with the built-in DAG):
                # place everything remaining to guarantee progress.
                ready = list(remaining)
            ready.sort()  # deterministic ordering within a stage
            stages.append(ready)
            placed.update(ready)
            remaining.difference_update(ready)

        if SUPERVISOR in selected_set:
            stages.append([SUPERVISOR])

        return stages
