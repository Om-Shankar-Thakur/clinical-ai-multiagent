"""
core.contracts
==============
Shared, serializable data structures passed between the planner, executor,
agents and supervisor. These are plain dataclasses with ``to_dict`` helpers so
they can be embedded directly in the JSON API response without extra plumbing.

None of these types contain behaviour or medical reasoning - they are contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


# --------------------------------------------------------------------------- #
#  Execution plan (produced by the planner, consumed by the executor)
# --------------------------------------------------------------------------- #
@dataclass
class ExecutionPlan:
    """
    A structured decision about which agents to run.

    Attributes
    ----------
    agents : list[str]
        Ordered set of agent names the planner selected.
    parallel : list[str]
        Subset of ``agents`` the planner believes may run concurrently.
        Treated as an optimisation hint; the executor still honours the
        dependency graph for correctness.
    reasoning : str
        Natural-language justification produced by the planner (LLM).
    source : str
        "llm" when produced by Gemini, "fallback" when the deterministic
        safety net was used (e.g. the LLM returned invalid JSON).
    """

    agents: list[str] = field(default_factory=list)
    parallel: list[str] = field(default_factory=list)
    reasoning: str = ""
    source: str = "llm"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
#  Agent result (produced by every agent's execute())
# --------------------------------------------------------------------------- #
@dataclass
class AgentResult:
    """
    Uniform return type for every agent run.

    Attributes
    ----------
    agent : str
        Registry name of the agent that produced this result.
    output : dict
        The agent's domain output (backward-compatible shape per agent).
    confidence : float
        The agent's self-assessed confidence in its own output, 0.0 - 1.0.
    status : str
        "success" | "error" | "skipped".
    error : str | None
        Error message when ``status == "error"``.
    input_assessment : dict | None
        Optional record of the confidence/quality the agent observed in the
        upstream outputs it consumed (confidence chaining).
    """

    agent: str
    output: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    status: str = "success"
    error: str | None = None
    input_assessment: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
#  Trace record (one per agent execution)
# --------------------------------------------------------------------------- #
@dataclass
class TraceRecord:
    """A single agent's execution telemetry."""

    execution_id: str
    agent: str
    start_time: str
    end_time: str
    latency_ms: float
    status: str
    error: str | None = None
    confidence: float | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
