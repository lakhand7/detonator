"""Proxy seam. Importing this package populates the Transport registry (§5, §16).

Import-wiring is the one tax: a transport registers only if its module runs, so the
seam's V1 kinds are imported here. New transport (e.g. deferred http_sse) = a new
@register-ed class added to this import list.
"""

from detonator.proxy.transport import Transport, get, register
from detonator.proxy import stdio as _stdio  # noqa: F401  registers "stdio"

__all__ = ["Transport", "get", "register"]
