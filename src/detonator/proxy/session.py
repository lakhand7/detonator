"""The proxy core (DESIGN.md §6): an imperative shell around pure decisions.

ProxySession is a humble object — wiring only, no domain logic. It owns the one piece
of session state, an id->tool correlation map (a JSON-RPC result carries only `id`, not
the tool name), and forwards ORIGINAL bytes in both directions. Poison happens only on
s2c and is wired in behind the InjectTransform seam in Module 3; in record mode
(inject=None) this is a transparent passthrough+log relay.
"""

import asyncio
import json
import sys

from detonator.model.scenario import Inject
from detonator.poison import get as get_strategy, should_poison
from detonator.proxy.transport import Transport


def _as_message(direction: str, line: bytes):
    """Parse a wire line into a JSON-RPC object, or return None if it isn't one.

    MCP stdio is newline-delimited JSON-RPC, but real servers sometimes leak non-protocol lines
    onto stdout (e.g. a logging library with a stdout sink). Such a line is not a message: skip it
    rather than crash the pump, and do NOT forward it (that would just corrupt the peer's stream).
    It's surfaced on stderr so the upstream's misbehaviour stays visible.
    """
    try:
        parsed = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    preview = line[:200].decode("utf-8", "replace").strip()
    print(f"detonate proxy: skipped non-JSON-RPC {direction} line: {preview}", file=sys.stderr, flush=True)
    return None


class ProxySession:
    def __init__(self, t: Transport, inject: Inject | None, log):
        self.t = t
        self.inject = inject
        self.log = log
        self._pending: dict[object, str] = {}

    async def run(self) -> None:
        await asyncio.gather(self._pump_c2s(), self._pump_s2c())

    async def _pump_c2s(self) -> None:
        async for line in self.t.c2s():
            m = _as_message("c2s", line)
            if m is None:  # stray non-JSON-RPC line (e.g. an upstream log) — skip, don't forward
                continue
            if m.get("method") == "tools/call":  # record id->tool for correlation
                params = m.get("params") or {}
                self._pending[m.get("id")] = params.get("name", "")
            self.log.append("c2s", m)
            await self.t.to_server(line)  # forward ORIGINAL bytes

    async def _pump_s2c(self) -> None:
        async for line in self.t.s2c():
            m = _as_message("s2c", line)
            if m is None:  # stray non-JSON-RPC line (e.g. an upstream log) — skip, don't forward
                continue
            tool = self._pending.pop(m.get("id"), None)  # correlated tool for this result
            if self.inject and should_poison(m, tool, self.inject):
                m = get_strategy(self.inject.strategy)(self.inject).apply(m, self.inject.payload)
                line = (json.dumps(m) + "\n").encode()  # re-serialize the one edited message
                self.log.append("s2c", m, poisoned=True)
            else:
                self.log.append("s2c", m)  # forward ORIGINAL bytes unchanged
            await self.t.to_client(line)
