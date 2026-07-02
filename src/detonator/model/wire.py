"""Envelope over verbatim JSON-RPC bytes + the one projection V1 tripwires need (§4).

The proxy is byte-faithful, so `LoggedMessage.raw` is the verbatim JSON-RPC object.
`tool_calls()` projects the c2s `tools/call` stream that tripwires consume.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class LoggedMessage(BaseModel):
    model_config = ConfigDict(frozen=True)
    i: int
    dir: Literal["c2s", "s2c"]  # client->server / server->client
    raw: dict  # verbatim JSON-RPC object (proxy is byte-faithful)
    poisoned: bool = False


class ToolCall(BaseModel):  # the only projection V1 tripwires need
    model_config = ConfigDict(frozen=True)
    i: int
    id: object
    name: str
    arguments: dict


def tool_calls(log: list[LoggedMessage]) -> list[ToolCall]:
    out = []
    for m in log:
        if m.dir == "c2s" and m.raw.get("method") == "tools/call":
            p = m.raw.get("params", {})
            out.append(
                ToolCall(
                    i=m.i,
                    id=m.raw.get("id"),
                    name=p.get("name", ""),
                    arguments=p.get("arguments", {}),
                )
            )
    return out
