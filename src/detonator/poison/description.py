"""`description` (where=description) — append to a tool's description (DESIGN.md §9).

Appending (not replacing) is stealthier and preserves the tool's real function. The
target tool name comes from the inject rule the transform was constructed with.
"""

from detonator.model.scenario import Inject
from detonator.poison.strategy import register


@register("description")
class RewriteDescription:
    def __init__(self, inject: Inject | None = None):
        self.inject = inject

    def apply(self, raw: dict, payload: str) -> dict:
        target = self.inject.tool if self.inject else None
        tools = (raw.get("result") or {}).get("tools", [])
        for tool in tools:
            if isinstance(tool, dict) and (target is None or tool.get("name") == target):
                tool["description"] = tool.get("description", "") + "\n" + payload
        return raw
