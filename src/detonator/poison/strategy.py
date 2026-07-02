"""Seam 2 — InjectTransform (DESIGN.md §5). Protocol + module registry + @register.

Identical shape to the transport and tripwire seams. `apply` is pure: raw -> rewritten
raw (the exact algorithms live in §9 / splice.py + description.py). V1 kinds: splice,
description; overwrite/error/structured_content_tamper are deferred (§20).
"""

from typing import Protocol

_REGISTRY: dict[str, type] = {}


def register(key: str):
    def deco(cls):
        _REGISTRY[key] = cls  # return unchanged; only record it
        return cls

    return deco


def get(key: str) -> type:
    return _REGISTRY[key]


class InjectTransform(Protocol):
    def apply(self, raw: dict, payload: str) -> dict: ...  # pure: raw -> rewritten raw (§9)
