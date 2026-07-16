"""
core
====
Framework-level abstractions for the Planner-Executor multi-agent architecture.

This package contains NO medical reasoning. It provides the plumbing that the
orchestrator, planner, executor and agents build on:

- contracts   : shared, serializable data structures (plan, agent result, trace)
- base_agent  : the uniform BaseAgent interface every executable agent implements
- registry    : name -> agent resolution (so the executor never imports agents)
- memory      : in-memory shared context / execution history
- tracing     : per-agent execution records + execution-id generation
"""

from core.contracts import AgentResult, ExecutionPlan, TraceRecord
from core.base_agent import BaseAgent
from core.registry import AgentRegistry
from core.memory import ClinicalMemory
from core.tracing import ExecutionTrace, new_execution_id

__all__ = [
    "AgentResult",
    "ExecutionPlan",
    "TraceRecord",
    "BaseAgent",
    "AgentRegistry",
    "ClinicalMemory",
    "ExecutionTrace",
    "new_execution_id",
]
