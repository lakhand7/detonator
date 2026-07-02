"""Eval seam. Importing this package populates the Tripwire registry (§5, §16).

Import-wiring tax: a tripwire registers only if its module runs, so both V1 kinds are
imported here. New tripwire (e.g. deferred egress) = a new @register-ed class reading a
new EvidenceContext field, added to this list — zero evaluator change.
"""

from detonator.eval.tripwire import Tripwire, get, register
from detonator.eval import canary_exfil as _canary  # noqa: F401  registers "canary_exfil"
from detonator.eval import unauthorized_tool as _unauth  # noqa: F401  registers "unauthorized_tool"
from detonator.eval.run import evaluate, load_log, load_run_scenario, verdict_from

__all__ = [
    "Tripwire",
    "get",
    "register",
    "evaluate",
    "verdict_from",
    "load_log",
    "load_run_scenario",
]
