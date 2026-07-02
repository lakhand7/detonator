"""The proxy core (DESIGN.md §6): an imperative shell around pure decisions.

ProxySession is a humble object — wiring only, no domain logic. It owns the one piece
of session state, an id->tool correlation map (a JSON-RPC result carries only `id`, not
the tool name), and forwards ORIGINAL bytes in both directions. Poison happens only on
s2c and is wired in behind the InjectTransform seam in Module 3; in record mode
(inject=None) this is a transparent passthrough+log relay.
"""

import asyncio
import json

from detonator.model.scenario import Inject
from detonator.proxy.transport import Transport


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
            m = json.loads(line)
            if m.get("method") == "tools/call":  # record id->tool for correlation
                params = m.get("params") or {}
                self._pending[m.get("id")] = params.get("name", "")
            self.log.append("c2s", m)
            await self.t.to_server(line)  # forward ORIGINAL bytes

    async def _pump_s2c(self) -> None:
        async for line in self.t.s2c():
            m = json.loads(line)
            self._pending.pop(m.get("id"), None)  # correlation cleanup (poison consumes it in M3)
            self.log.append("s2c", m)
            await self.t.to_client(line)  # forward ORIGINAL bytes
