"""Target runbook parsing + MCP config patching (DESIGN.md §11, §12).

`config apply` points a target's MCP server at `detonate proxy`; `config restore` puts it
back. Idempotent: the pristine original is backed up only if no backup exists yet, so
re-applying per variant never overwrites it with an already-patched config. The run dir is
NOT baked into the entry — it propagates to the proxy via $DETONATE_RUN_DIR at runtime (§8).
"""

import json
from pathlib import Path

import yaml

BACKUP_SUFFIX = ".detonate-bak"


def parse_runbook(path: str | Path) -> dict:
    """Extract the '---'-delimited YAML front-matter block from a runbook markdown file."""
    text = Path(path).read_text()
    if not text.lstrip().startswith("---"):
        raise ValueError(f"runbook {path} has no '---' front-matter block")
    parts = text.split("---", 2)  # ['', '<yaml>', '<prose>']
    if len(parts) < 3:
        raise ValueError(f"runbook {path} front-matter is not closed with '---'")
    data = yaml.safe_load(parts[1]) or {}
    if not isinstance(data, dict):
        raise ValueError(f"runbook {path} front-matter is not a mapping")
    return data


def proxy_entry(scenario: str | Path, server: str) -> dict:
    """The MCP server entry that launches `detonate proxy` as the target's server (§11)."""
    return {
        "command": "detonate",
        "args": ["proxy", "--scenario", str(Path(scenario).resolve()), "--server", server],
    }


def _config_path(runbook: Path, rb: dict) -> Path:
    p = Path(rb["mcp_config_path"])
    return p if p.is_absolute() else (runbook.parent / p).resolve()


def _backup_of(cfg_path: Path) -> Path:
    return cfg_path.with_name(cfg_path.name + BACKUP_SUFFIX)


def apply_config(runbook: str | Path, scenario: str | Path) -> Path:
    """Patch the target's MCP config to launch the proxy; back up the original once.

    Returns the backup path.
    """
    runbook = Path(runbook)
    rb = parse_runbook(runbook)
    cfg_path = _config_path(runbook, rb)
    server = rb["mcp_server_name"]
    backup = _backup_of(cfg_path)
    if not backup.exists():  # idempotent: preserve only the pristine original
        backup.write_text(cfg_path.read_text())
    cfg = json.loads(cfg_path.read_text())
    cfg.setdefault("mcpServers", {})[server] = proxy_entry(scenario, server)
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
    return backup


def restore_config(runbook: str | Path) -> Path:
    """Restore the target's MCP config from backup and remove the backup. Returns config path."""
    runbook = Path(runbook)
    rb = parse_runbook(runbook)
    cfg_path = _config_path(runbook, rb)
    backup = _backup_of(cfg_path)
    if not backup.exists():
        raise FileNotFoundError(f"no backup at {backup}")
    cfg_path.write_text(backup.read_text())
    backup.unlink()
    return cfg_path
