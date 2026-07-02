"""Seam 1 — Transport (DESIGN.md §5). Protocol + module registry + @register decorator.

Structural contract: implementations don't inherit or import the core; the dependency
arrow points inward, so fakes are free (§17). stdio is the only V1 kind; http_sse is
deferred (§20) and would slot in as another @register-ed class behind this same seam.
"""

from typing import AsyncIterator, Protocol

_REGISTRY: dict[str, type] = {}


def register(key: str):
    def deco(cls):
        _REGISTRY[key] = cls  # return unchanged; only record it
        return cls

    return deco


def get(key: str) -> type:
    return _REGISTRY[key]


class Transport(Protocol):
    """Byte relay between three parties — every name below is relative to the proxy:

    - **us**: the ``detonate proxy`` process implementing this Transport (the
      man-in-the-middle running the relay).
    - **client (agent)**: the target agent under test. We patched its MCP config to point at
      ``detonate proxy``, so it launched us as its MCP server and thinks *we* are the server —
      it writes JSON-RPC requests to our stdin and reads responses from our stdout.
    - **upstream server**: the real MCP server (e.g. ``@modelcontextprotocol/server-slack``)
      that we spawn as a subprocess and relay to. "Upstream" = behind us, further from the agent.

    Topology:   client (agent)  ->  us (proxy)  ->  upstream server
    Request leg:  c2s() then to_server()   (client -> us -> upstream)
    Response leg: s2c() then to_client()   (upstream -> us -> client)
    """

    def c2s(self) -> AsyncIterator[bytes]: ...  # bytes from client (agent) -> us
    def s2c(self) -> AsyncIterator[bytes]: ...  # bytes from upstream server -> us
    async def to_server(self, b: bytes) -> None: ...  # bytes from us -> upstream server
    async def to_client(self, b: bytes) -> None: ...  # bytes from us -> client (agent)
