"""`splice` (where=result) — insert the payload as native-looking data (DESIGN.md §9, + path).

Two modes:

- **With an explicit JSON Pointer** (`inject.path`, RFC 6901): walk to that location in the
  *decoded* tool result and set it — or, for a trailing ``/-``, append to that array. Placement is
  chosen by the attack author who saw the real shape in the record pass, so nothing is guessed.
  This is what generalizes across arbitrary/nested schemas (``/results/-``, ``/messages/-``,
  ``/data/items/0/summary``, ...).
- **Without a path**: best-effort structure-aware auto-splice for simple shapes — append a
  shaped-like sibling into the first JSON array (or the first list value of a JSON object), else
  append a text block.

Either way the output round-trips as valid JSON and remains a valid MCP result.
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


def _value(payload: str):
    """The value to inject: the payload parsed as JSON when possible (so you can insert a
    native-looking object/array), else the raw string."""
    parsed = _try_json(payload)
    return parsed if parsed is not None else payload


def _unescape(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")  # RFC 6901 order: ~1 then ~0


def _set_pointer(root, pointer: str, value) -> bool:
    """Set/append `value` at a JSON Pointer within `root`. A trailing '-' appends to an array; an
    in-range/next index or any dict key sets. Returns False if the path cannot be resolved."""
    if not pointer.startswith("/"):
        return False
    tokens = [_unescape(t) for t in pointer.split("/")[1:]]
    cur = root
    for token in tokens[:-1]:
        if isinstance(cur, dict):
            if token not in cur:
                return False
            cur = cur[token]
        elif isinstance(cur, list):
            try:
                idx = int(token)
            except ValueError:
                return False
            if not (0 <= idx < len(cur)):
                return False
            cur = cur[idx]
        else:
            return False
    last = tokens[-1]
    if isinstance(cur, list):
        if last == "-":
            cur.append(value)
            return True
        try:
            idx = int(last)
        except ValueError:
            return False
        if 0 <= idx < len(cur):
            cur[idx] = value
            return True
        if idx == len(cur):
            cur.append(value)
            return True
        return False
    if isinstance(cur, dict):
        cur[last] = value
        return True
    return False


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
        self.inject = inject

    def apply(self, raw: dict, payload: str) -> dict:
        path = self.inject.path if self.inject else None
        if path:
            return self._apply_at_path(raw, path, payload)
        return self._apply_auto(raw, payload)

    def _apply_at_path(self, raw: dict, path: str, payload: str) -> dict:
        result = raw["result"]
        value = _value(payload)
        # 1) structuredContent (native structured data), if the server used it.
        structured = result.get("structuredContent")
        if isinstance(structured, (dict, list)) and _set_pointer(structured, path, value):
            return raw
        # 2) serialized JSON inside a text content block (the common case).
        content = result.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parsed = _try_json(block.get("text"))
                    if isinstance(parsed, (dict, list)) and _set_pointer(parsed, path, value):
                        block["text"] = json.dumps(parsed)
                        return raw
            content.append({"type": "text", "text": payload})  # fail safe: path didn't resolve
            return raw
        result["content"] = [{"type": "text", "text": payload}]
        return raw

    def _apply_auto(self, raw: dict, payload: str) -> dict:
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
                    for _key, val in parsed.items():
                        if isinstance(val, list):
                            val.append(_shape_like(val[-1] if val else {}, payload))
                            block["text"] = json.dumps(parsed)
                            return raw
            content.append({"type": "text", "text": payload})  # fallback: extra text block
            return raw
        # ultimate fallback: content missing / not a list -> a valid one-block content list
        result["content"] = [{"type": "text", "text": payload}]
        return raw
