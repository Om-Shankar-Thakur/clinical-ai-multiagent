"""
core.base_agent
===============
The uniform interface every executable agent (or agent adapter) implements.

The executor depends only on this abstraction - never on concrete agent
classes - so new agents can be added by registering an adapter, without any
change to executor code (Open/Closed principle).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.contracts import AgentResult


class BaseAgent(ABC):
    """
    Contract for anything the executor can run.

    Subclasses declare:

    - ``name``          : the registry key (e.g. "symptom_agent")
    - ``dependencies``  : registry names whose output must exist before this
                          agent runs. Used by the executor to build safe
                          execution stages (topological layering). An agent
                          with no dependencies may run in the first stage.

    and implement ``execute(memory)`` which reads its inputs from shared
    memory and returns an :class:`AgentResult`.
    """

    #: Registry key. Must be overridden by every concrete agent.
    name: str = "base_agent"

    #: Names of agents this agent consumes output from. Overridable.
    dependencies: list[str] = []

    @abstractmethod
    def execute(self, memory) -> AgentResult:
        """
        Run the agent against the shared :class:`~core.memory.ClinicalMemory`.

        Implementations MUST NOT raise for expected clinical edge cases; they
        should return an :class:`AgentResult` with ``status="error"`` and a
        safe ``output`` so the executor can continue and the supervisor can
        flag it. Unexpected exceptions are caught and traced by the executor.
        """
        raise NotImplementedError
