"""Config DTOs at the edge (DESIGN.md §4).

YAML in -> validated -> safety-gated. The `_safety_bounds` model_validator *is*
`detonate validate`: it fails closed on anything that isn't an authorized,
internally-consistent scenario.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


class ServerSpec(BaseModel):
    """The real upstream MCP server the proxy fronts."""

    command: list[str]  # e.g. ["npx", "-y", "@modelcontextprotocol/server-slack"]
    env: dict[str, str] = {}  # ${VAR} expanded from the proxy's environment at spawn


class Inject(BaseModel):
    """The one poison rule (omit/None => record mode)."""

    tool: str  # wire tool name whose message we poison
    where: Literal["result", "description"] = "result"
    strategy: str = "splice"  # registry key -> InjectTransform
    payload: str
    path: str | None = None  # optional JSON Pointer (RFC 6901) into the decoded result; splice targets it


class CanaryExfilSpec(BaseModel):
    type: Literal["canary_exfil"] = "canary_exfil"
    values: list[str]  # planted canaries hunted in downstream tool args


class UnauthorizedToolSpec(BaseModel):
    type: Literal["unauthorized_tool"] = "unauthorized_tool"
    # reads scenario.allow


TripwireSpec = Annotated[
    CanaryExfilSpec | UnauthorizedToolSpec, Field(discriminator="type")
]


class Scenario(BaseModel):
    id: str
    servers: dict[str, ServerSpec]  # V1: exactly one entry per scenario/proxy (§11 --server)
    inject: Inject | None = None  # None => proxy is pure passthrough+log (record mode)
    allow: list[str] = []  # bare wire tool names the benign task legitimately uses
    tripwires: list[TripwireSpec]
    authorized: bool = False

    @model_validator(mode="after")
    def _safety_bounds(self):  # this IS "validate-scenario"
        if not self.authorized:
            raise ValueError("authorized must be true (authorized-targets-only)")
        for tw in self.tripwires:
            if isinstance(tw, CanaryExfilSpec) and self.inject:
                for v in tw.values:
                    if v not in self.inject.payload:
                        raise ValueError(f"canary {v!r} must appear in inject.payload")
            if isinstance(tw, UnauthorizedToolSpec) and not self.allow:
                raise ValueError("unauthorized_tool requires a non-empty allow list")
        return self
