"""Verdict of record (§4). Frozen so it serializes deterministically to report.json.

V1 status is binary: REACHABLE (a tripwire fired; exploit proven) vs UNREACHABLE
(the adversarial condition ran and nothing fired). POTENTIALLY_REACHABLE is deferred.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class TripwireResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: str
    fired: bool
    evidence: tuple[str, ...] = ()


class Verdict(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: Literal["REACHABLE", "UNREACHABLE"]
    results: tuple[TripwireResult, ...]
    repro: dict | None = None
