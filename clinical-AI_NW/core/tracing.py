"""
core.tracing
============
Execution telemetry.

Every run gets a single ``execution_id``. Each agent execution produces a
:class:`~core.contracts.TraceRecord` (start/end/latency/status/error/confidence
/reason). :class:`ExecutionTrace` collects them and serialises into the final
report so the whole run is observable end-to-end.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from core.contracts import TraceRecord


def new_execution_id() -> str:
    """Generate a unique execution id for a single orchestrator run."""
    return f"exec-{uuid.uuid4().hex[:12]}"


def utc_now_iso() -> str:
    """Timezone-aware UTC timestamp in ISO-8601 form."""
    return datetime.now(timezone.utc).isoformat()


class ExecutionTrace:
    """Ordered collection of per-agent trace records for one run."""

    def __init__(self, execution_id: str) -> None:
        self.execution_id = execution_id
        self._records: list[TraceRecord] = []

    def add(self, record: TraceRecord) -> None:
        self._records.append(record)

    @property
    def records(self) -> list[TraceRecord]:
        return list(self._records)

    def total_latency_ms(self) -> float:
        return round(sum(r.latency_ms for r in self._records), 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "total_latency_ms": self.total_latency_ms(),
            "steps": [r.to_dict() for r in self._records],
        }
