"""The evaluator (DESIGN.md §5) — a pure function of (scenario, log), so --replay is free.

`evaluate` builds the EvidenceContext, runs each scenario tripwire, and reduces the results
to the binary Verdict of record. `load_log`/`load_run_scenario` rehydrate a saved run so a
log.jsonl always yields the same Verdict.
"""

import json
from pathlib import Path

from detonator.model.context import EvidenceContext
from detonator.model.scenario import Scenario
from detonator.model.verdict import TripwireResult, Verdict
from detonator.model.wire import LoggedMessage
from detonator.eval.tripwire import get


def verdict_from(results: list[TripwireResult], log_ref: str) -> Verdict:
    fired = [r for r in results if r.fired]
    return Verdict(
        status="REACHABLE" if fired else "UNREACHABLE",
        results=tuple(results),
        repro={"log": log_ref, "fired": [r.type for r in fired]} if fired else None,
    )


def evaluate(scenario: Scenario, log, log_ref: str) -> Verdict:
    ctx = EvidenceContext(scenario=scenario, mcp_log=tuple(log))
    results = [get(s.type)(s).evaluate(ctx) for s in scenario.tripwires]
    return verdict_from(results, log_ref)


def load_log(path: str | Path) -> list[LoggedMessage]:
    lines = Path(path).read_text().splitlines()
    return [LoggedMessage(**json.loads(line)) for line in lines if line.strip()]


def load_run_scenario(path: str | Path) -> Scenario:
    """Rehydrate the scenario copy the proxy saved into the run dir (scenario.json)."""
    return Scenario(**json.loads(Path(path).read_text()))
