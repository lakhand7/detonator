"""stdio transport (DESIGN.md §5, §7): newline-delimited JSON over pipes.

Spawns ServerSpec.command as the upstream MCP server and relays this process's own
stdin/stdout (the agent "client") to/from it. This is the imperative shell — unit tests
drive ProxySession with a FakeTransport (§17); StdioTransport is exercised live.
"""

import asyncio
import os
import sys

from detonator.model.scenario import ServerSpec
from detonator.proxy.transport import register


async def _wrap_stdio() -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Wrap this process's stdin/stdout as asyncio streams (POSIX)."""
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
    w_transport, w_protocol = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    writer = asyncio.StreamWriter(w_transport, w_protocol, reader, loop)
    return reader, writer


@register("stdio")
class StdioTransport:
    def __init__(self, spec: ServerSpec):
        self.spec = spec
        self._proc: asyncio.subprocess.Process | None = None
        self._client_in: asyncio.StreamReader | None = None
        self._client_out: asyncio.StreamWriter | None = None

    async def start(self) -> None:
        env = dict(os.environ)
        env.update({k: os.path.expandvars(v) for k, v in self.spec.env.items()})  # ${VAR} at spawn
        self._proc = await asyncio.create_subprocess_exec(
            *self.spec.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            # stderr inherited: upstream diagnostics reach the terminal; stdout stays clean JSON-RPC.
            env=env,
        )
        self._client_in, self._client_out = await _wrap_stdio()

    async def c2s(self):
        assert self._client_in is not None
        async for line in self._client_in:
            yield line
        # client closed stdin (EOF) -> close upstream stdin so it can shut down (§8)
        if self._proc and self._proc.stdin and not self._proc.stdin.is_closing():
            self._proc.stdin.close()

    async def s2c(self):
        assert self._proc is not None and self._proc.stdout is not None
        async for line in self._proc.stdout:
            yield line

    async def to_server(self, b: bytes) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write(b)
        await self._proc.stdin.drain()

    async def to_client(self, b: bytes) -> None:
        assert self._client_out is not None
        self._client_out.write(b)
        await self._client_out.drain()

    async def aclose(self) -> None:
        # Close our stdout writer *inside* the loop so its __del__ doesn't fire a
        # "Event loop is closed" error after asyncio.run() tears the loop down.
        if self._client_out is not None:
            try:
                self._client_out.close()
                await self._client_out.wait_closed()
            except Exception:
                pass
        if self._proc is None or self._proc.returncode is not None:
            return
        try:
            if self._proc.stdin and not self._proc.stdin.is_closing():
                self._proc.stdin.close()
            await asyncio.wait_for(self._proc.wait(), timeout=5)
        except (asyncio.TimeoutError, ProcessLookupError):
            try:
                self._proc.kill()
            except ProcessLookupError:
                pass
