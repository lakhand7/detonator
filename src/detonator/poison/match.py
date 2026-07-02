"""The poison matcher (DESIGN.md §9) — pure `should_poison(raw, tool, inject) -> bool`.

Decides whether an s2c message is the one the active inject rule targets. `tool` is the
correlated tool name from the proxy's id->tool map (None if uncorrelated).
"""

from detonator.model.scenario import Inject


def should_poison(raw: dict, tool, inject: Inject) -> bool:
    if inject.where == "result":
        # raw has a `result` key AND the correlated tool is the inject target.
        return "result" in raw and tool == inject.tool
    if inject.where == "description":
        # raw.result.tools is a list containing the inject target (no id-correlation needed).
        tools = (raw.get("result") or {}).get("tools")
        return isinstance(tools, list) and any(
            isinstance(t, dict) and t.get("name") == inject.tool for t in tools
        )
    return False
