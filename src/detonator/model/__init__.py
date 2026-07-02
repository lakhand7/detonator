"""Schemas: pydantic DTOs at the config boundary, frozen value objects through the core.

DESIGN.md §4. Config (Scenario + members) is validated/safety-gated pydantic; wire,
context, and verdict objects are frozen and replay-stable (serialize to report.json).
"""

from detonator.model.scenario import (
    CanaryExfilSpec,
    Inject,
    Scenario,
    ServerSpec,
    TripwireSpec,
    UnauthorizedToolSpec,
)
from detonator.model.wire import LoggedMessage, ToolCall, tool_calls
from detonator.model.context import EvidenceContext
from detonator.model.verdict import TripwireResult, Verdict

__all__ = [
    "ServerSpec",
    "Inject",
    "CanaryExfilSpec",
    "UnauthorizedToolSpec",
    "TripwireSpec",
    "Scenario",
    "LoggedMessage",
    "ToolCall",
    "tool_calls",
    "EvidenceContext",
    "TripwireResult",
    "Verdict",
]
