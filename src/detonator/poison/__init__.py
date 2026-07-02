"""Poison seam. Importing this package populates the InjectTransform registry (§5, §16).

Import-wiring tax: a strategy registers only if its module runs, so both V1 kinds are
imported here. New strategy (e.g. deferred overwrite) = a new @register-ed class added
to this list.
"""

from detonator.poison.strategy import InjectTransform, get, register
from detonator.poison.match import should_poison
from detonator.poison import splice as _splice  # noqa: F401  registers "splice"
from detonator.poison import description as _description  # noqa: F401  registers "description"

__all__ = ["InjectTransform", "get", "register", "should_poison"]
