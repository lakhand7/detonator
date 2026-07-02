"""Seam 3 — Tripwire (DESIGN.md §5). Protocol + module registry + @register.

A tripwire reads exactly one EvidenceContext.<source> field (dependency inversion on the
evidence source = the detection tiering). V1 kinds read `mcp_log`; egress/fs_audit/syscall/
approval_bypass are deferred (§20) — each a new class reading a new context field, with zero
evaluator change.
"""

from typing import Protocol

from detonator.model.context import EvidenceContext
from detonator.model.verdict import TripwireResult

_REGISTRY: dict[str, type] = {}


def register(key: str):
    def deco(cls):
        _REGISTRY[key] = cls  # return unchanged; only record it
        return cls

    return deco


def get(key: str) -> type:
    return _REGISTRY[key]


class Tripwire(Protocol):
    source: str  # the EvidenceContext field it consumes

    def evaluate(self, ctx: EvidenceContext) -> TripwireResult: ...
