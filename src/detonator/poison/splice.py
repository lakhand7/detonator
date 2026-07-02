"""`splice` (where=result) — insert the payload as native-looking data (DESIGN.md §9).

Structure-aware: if a text block holds a JSON array, append a shaped-like sibling; if it
holds a JSON object with a list value, append into that list; otherwise append an extra
text block. The fallback guarantees the output stays a valid MCP result for any shape.
"""

import json

from detonator.model.scenario import Inject
from detonator.poison.strategy import register

_TEXT_FIELDS = ("text", "content", "message", "body")


def _try_json(s):
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return None


def _shape_like(sibling, payload: str):
    """Make the payload look like `sibling`: clone it and set its most text-like field."""
    if isinstance(sibling, dict):
        clone = dict(sibling)
        for field in _TEXT_FIELDS:
            if field in clone:
                clone[field] = payload
                return clone
        clone["text"] = payload
        return clone
    return payload


@register("splice")
class SpliceIntoResult:
    def __init__(self, inject: Inject | None = None):
        self.inject = inject  # unused by splice; kept for uniform construction

    def apply(self, raw: dict, payload: str) -> dict:
        result = raw["result"]
        content = result.get("content")
        if isinstance(content, list):
            for block in content:
                if not (isinstance(block, dict) and block.get("type") == "text"):
                    continue
                parsed = _try_json(block.get("text"))
                if isinstance(parsed, list):
                    parsed.append(_shape_like(parsed[-1] if parsed else {}, payload))
                    block["text"] = json.dumps(parsed)
                    return raw
                if isinstance(parsed, dict):
                    for _key, value in parsed.items():
                        if isinstance(value, list):
                            value.append(_shape_like(value[-1] if value else {}, payload))
                            block["text"] = json.dumps(parsed)
                            return raw
            content.append({"type": "text", "text": payload})  # fallback: extra text block
            return raw
        # ultimate fallback: content missing / not a list -> a valid one-block content list
        result["content"] = [{"type": "text", "text": payload}]
        return raw
