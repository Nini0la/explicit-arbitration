from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class TraceEntry:
    run_id: str
    timestamp_utc: str
    component: str
    step: str
    input_payload: dict[str, Any]
    output_payload: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


def new_trace_entry(
    run_id: str,
    component: str,
    step: str,
    input_payload: dict[str, object],
    output_payload: dict[str, object],
    metadata: dict[str, object] | None = None,
) -> TraceEntry:
    return TraceEntry(
        run_id=run_id,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        component=component,
        step=step,
        input_payload=dict(input_payload),
        output_payload=dict(output_payload),
        metadata=dict(metadata or {}),
    )


def record_trace(store: list[TraceEntry], entry: TraceEntry) -> None:
    store.append(entry)
