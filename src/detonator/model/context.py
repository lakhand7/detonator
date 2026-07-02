"""Dependency inversion on the evidence source = the detection tiering (§4).

A tripwire reads exactly one `EvidenceContext.<source>` field. V1 populates only
`mcp_log`; egress/fs_events/syscalls are deferred (need the isolation tier, §20) and
stay empty tuples so new detection tiers slot in with zero evaluator change.
"""

from pydantic import BaseModel, ConfigDict

from detonator.model.scenario import Scenario
from detonator.model.wire import LoggedMessage


class EvidenceContext(BaseModel):
    model_config = ConfigDict(frozen=True)
    scenario: Scenario
    mcp_log: tuple[LoggedMessage, ...]
    egress: tuple = ()  # deferred (needs netns)
    fs_events: tuple = ()  # deferred (needs cgroup)
    syscalls: tuple = ()  # deferred
