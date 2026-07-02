"""Test doubles for the proxy seam (DESIGN.md §17).

FakeTransport lets us drive ProxySession with canned bytes — no subprocess, no
network — and capture exactly what the session forwards in each direction.
"""
import json


class FakeTransport:
    """Canned c2s/s2c byte streams; records what the session writes back out."""

    def __init__(self, c2s_lines, s2c_lines):
        self._c2s = list(c2s_lines)
        self._s2c = list(s2c_lines)
        self.to_server_calls: list[bytes] = []
        self.to_client_calls: list[bytes] = []

    async def c2s(self):
        for b in self._c2s:
            yield b

    async def s2c(self):
        for b in self._s2c:
            yield b

    async def to_server(self, b: bytes) -> None:
        self.to_server_calls.append(b)

    async def to_client(self, b: bytes) -> None:
        self.to_client_calls.append(b)


class RecordingLog:
    """A MessageLog stand-in that captures append() calls instead of writing a file."""

    def __init__(self):
        self.entries: list[tuple[str, dict, bool]] = []

    def append(self, dir_: str, raw: dict, poisoned: bool = False):
        self.entries.append((dir_, raw, poisoned))
        return None


def jline(obj) -> bytes:
    """Serialize obj to a newline-terminated JSON line (the stdio wire framing, §7)."""
    return (json.dumps(obj) + "\n").encode()
