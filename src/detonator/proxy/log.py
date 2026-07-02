"""JSON-RPC message log + run-directory resolution (DESIGN.md §8).

The proxy streams one LoggedMessage per line to <run-dir>/log.jsonl. Fixtures are just
saved log.jsonl files (§17). Run-dir precedence: --run-dir > $DETONATE_RUN_DIR >
runs/<UTC-ISO>/, and runs/latest is repointed at the active run each start.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

from detonator.model.wire import LoggedMessage


class MessageLog:
    """Append LoggedMessages and stream them to <path> as newline-delimited JSON."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._i = 0
        self._fh = None
        self.messages: list[LoggedMessage] = []

    def append(self, dir_: str, raw: dict, poisoned: bool = False) -> LoggedMessage:
        m = LoggedMessage(i=self._i, dir=dir_, raw=raw, poisoned=poisoned)
        self._i += 1
        self.messages.append(m)
        if self._fh is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = self.path.open("w", encoding="utf-8")
        self._fh.write(m.model_dump_json() + "\n")
        self._fh.flush()
        return m

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> "MessageLog":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def resolve_run_dir(run_dir: str | Path | None = None, *, base: str | Path = "runs") -> Path:
    """Resolve + create the run directory and repoint <base>/latest at it (§8)."""
    if run_dir:
        d = Path(run_dir)
    elif os.environ.get("DETONATE_RUN_DIR"):
        d = Path(os.environ["DETONATE_RUN_DIR"])
    else:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        d = Path(base) / ts
    d.mkdir(parents=True, exist_ok=True)
    _update_latest(Path(base), d)
    return d


def _update_latest(base: Path, target: Path) -> None:
    base.mkdir(parents=True, exist_ok=True)
    latest = base / "latest"
    try:
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(target.resolve())
    except OSError:
        pass  # symlinks unsupported on some filesystems; non-fatal per §8
