# execution/clinical_executor.py

"""
ClinicalExecutor
================
The mechanical runner. It executes an :class:`~core.contracts.ExecutionPlan` and
NOTHING ELSE - it contains no medical reasoning.

Responsibilities (exactly the ones specified):

- resolve agents from the :class:`~core.registry.AgentRegistry` (never imports them)
- execute sequential stages
- execute agents within a stage in parallel
- collect outputs into shared :class:`~core.memory.ClinicalMemory`
- record execution metadata (a :class:`~core.contracts.TraceRecord` per agent)
- return the :class:`~core.tracing.ExecutionTrace`

Concurrency model
-----------------
Agents within one stage never depend on one another (guaranteed by
:class:`~execution.plan_normalizer.PlanNormalizer`), so they run in a thread
pool. Worker threads only *read* memory and *return* their result; the executor
thread performs all memory writes and trace recording after the stage completes,
so there are no data races on memory.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.contracts import AgentResult, ExecutionPlan, TraceRecord
from core.memory import ClinicalMemory
from core.registry import AgentRegistry
from core.tracing import ExecutionTrace, new_execution_id, utc_now_iso
from execution.plan_normalizer import PlanNormalizer

logger = logging.getLogger(__name__)


class ClinicalExecutor:
    def __init__(self, registry: AgentRegistry, memory: ClinicalMemory) -> None:
        self.registry = registry
        self.memory = memory
        self._normalizer = PlanNormalizer(registry)

    # ------------------------------------------------------------------ #
    def execute(self, plan: ExecutionPlan, execution_id: str | None = None) -> ExecutionTrace:
        execution_id = execution_id or new_execution_id()
        trace = ExecutionTrace(execution_id)

        stages = self._normalizer.to_stages(plan)
        planned = set(plan.agents)
        logger.info("[executor] execution_id=%s stages=%s", execution_id, stages)

        for stage in stages:
            if len(stage) == 1:
                outcomes = [self._invoke(stage[0])]
            else:
                outcomes = self._invoke_parallel(stage)

            # Single-threaded commit: write memory + trace in a stable order.
            for name, result, timing in sorted(outcomes, key=lambda o: o[0]):
                self.memory.record_agent_result(result)
                record = TraceRecord(
                    execution_id=execution_id,
                    agent=name,
                    start_time=timing["start"],
                    end_time=timing["end"],
                    latency_ms=timing["latency_ms"],
                    status=result.status,
                    error=result.error,
                    confidence=result.confidence,
                    reason=(
                        "planner-selected" if name in planned
                        else "added by dependency closure"
                    ),
                )
                trace.add(record)
                self.memory.record_trace(record)

        return trace

    # ------------------------------------------------------------------ #
    def _invoke_parallel(self, stage: list[str]):
        outcomes = []
        with ThreadPoolExecutor(max_workers=len(stage)) as pool:
            futures = {pool.submit(self._invoke, name): name for name in stage}
            for future in as_completed(futures):
                outcomes.append(future.result())
        return outcomes

    def _invoke(self, name: str):
        """Run one agent, timing it. Never raises; converts errors to results."""
        start_perf = time.perf_counter()
        start_iso = utc_now_iso()
        try:
            agent = self.registry.get(name)
            result = agent.execute(self.memory)
            if not isinstance(result, AgentResult):  # defensive
                result = AgentResult(agent=name, output={}, confidence=0.0)
        except Exception as e:  # noqa: BLE001 - backstop; adapters catch their own
            logger.exception("[executor] agent '%s' raised", name)
            result = AgentResult(
                agent=name, output={}, confidence=0.0, status="error", error=str(e)
            )
        latency_ms = round((time.perf_counter() - start_perf) * 1000, 3)
        timing = {"start": start_iso, "end": utc_now_iso(), "latency_ms": latency_ms}
        return name, result, timing
