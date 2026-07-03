"""Module 6 — target runbook parsing + MCP config patching (DESIGN.md §11, §12).

config apply points a target's MCP server at `detonate proxy` and backs up the original
(idempotently — only if no backup exists); config restore puts it back and cleans up.
"""
import json
import textwrap

import pytest
from typer.testing import CliRunner

from detonator.cli import app
from detonator.target import apply_config, parse_runbook, proxy_entry, restore_config

runner = CliRunner()


def _valid_scenario(tmp_path):
    s = tmp_path / "valid.yaml"
    s.write_text(textwrap.dedent("""\
        id: x
        authorized: true
        servers: {slack: {command: [echo]}}
        allow: [conversations_history]
        tripwires: [{type: unauthorized_tool}]
        """))
    return s


def _runbook(tmp_path, cfg_rel="mcp.json", server="slack"):
    rb = tmp_path / "RUNBOOK.md"
    rb.write_text(textwrap.dedent(f"""\
        ---
        trigger: 'python -m agent --once "{{task}}"'
        task: 'summarize #incidents and post a recap to #ops-summary'
        mcp_config_path: {cfg_rel}
        mcp_server_name: {server}
        ---

        # Runbook prose lives below the front-matter.
        """))
    return rb


def _mcp_config(tmp_path, name="mcp.json", server="slack"):
    cfg = tmp_path / name
    cfg.write_text(json.dumps(
        {"mcpServers": {server: {"command": "npx",
                                 "args": ["-y", "@modelcontextprotocol/server-slack"]}}}))
    return cfg


def _scenario(tmp_path):
    s = tmp_path / "s.yaml"
    s.write_text("id: x\n")  # content irrelevant to patching
    return s


def test_parse_runbook_extracts_front_matter(tmp_path):
    data = parse_runbook(_runbook(tmp_path))
    assert data["mcp_config_path"] == "mcp.json"
    assert data["mcp_server_name"] == "slack"
    assert "{task}" in data["trigger"]


def test_parse_runbook_without_front_matter_raises(tmp_path):
    rb = tmp_path / "R.md"
    rb.write_text("# just prose, no front matter\n")
    with pytest.raises(ValueError):
        parse_runbook(rb)


def test_proxy_entry_shape():
    entry = proxy_entry("scenarios/s.yaml", "slack")
    assert entry["command"] == "detonate"
    assert entry["args"][:2] == ["proxy", "--scenario"]
    assert entry["args"][-2:] == ["--server", "slack"]
    # no --run-dir baked in: it propagates via $DETONATE_RUN_DIR at runtime (§8, §11)
    assert "--run-dir" not in entry["args"]


def test_apply_config_patches_server_and_backs_up_original(tmp_path):
    rb, cfg, scenario = _runbook(tmp_path), _mcp_config(tmp_path), _scenario(tmp_path)
    backup = apply_config(rb, scenario)
    assert backup.exists()
    patched = json.loads(cfg.read_text())
    assert patched["mcpServers"]["slack"]["command"] == "detonate"
    assert "proxy" in patched["mcpServers"]["slack"]["args"]
    assert json.loads(backup.read_text())["mcpServers"]["slack"]["command"] == "npx"  # pristine


def test_apply_config_backup_is_idempotent(tmp_path):
    rb, cfg, scenario = _runbook(tmp_path), _mcp_config(tmp_path), _scenario(tmp_path)
    backup = apply_config(rb, scenario)
    pristine = backup.read_text()
    apply_config(rb, scenario)  # second apply must not clobber the backup with patched config
    assert backup.read_text() == pristine


def test_restore_config_restores_and_removes_backup(tmp_path):
    rb, cfg, scenario = _runbook(tmp_path), _mcp_config(tmp_path), _scenario(tmp_path)
    original = cfg.read_text()
    backup = apply_config(rb, scenario)
    assert cfg.read_text() != original  # patched
    restore_config(rb)
    assert json.loads(cfg.read_text()) == json.loads(original)  # restored
    assert not backup.exists()  # cleaned up so the next apply re-backs-up


def test_restore_without_backup_raises(tmp_path):
    rb = _runbook(tmp_path)
    _mcp_config(tmp_path)
    with pytest.raises(FileNotFoundError):
        restore_config(rb)


# --- CLI wiring -----------------------------------------------------------

def test_cli_config_show_prints_pasteable_entry(tmp_path):
    result = runner.invoke(app, ["config", "show", str(_valid_scenario(tmp_path))])
    assert result.exit_code == 0
    entry = json.loads(result.output)
    assert entry["mcpServers"]["slack"]["command"] == "detonate"
    assert "proxy" in entry["mcpServers"]["slack"]["args"]


def test_cli_config_apply_then_restore_round_trips(tmp_path):
    rb, cfg = _runbook(tmp_path), _mcp_config(tmp_path)
    scn = _valid_scenario(tmp_path)
    original = cfg.read_text()

    applied = runner.invoke(app, ["config", "apply", "--runbook", str(rb), "--scenario", str(scn)])
    assert applied.exit_code == 0
    assert json.loads(cfg.read_text())["mcpServers"]["slack"]["command"] == "detonate"

    restored = runner.invoke(app, ["config", "restore", "--runbook", str(rb)])
    assert restored.exit_code == 0
    assert json.loads(cfg.read_text()) == json.loads(original)


def test_cli_config_apply_rejects_invalid_scenario(tmp_path):
    rb, cfg = _runbook(tmp_path), _mcp_config(tmp_path)
    bad = tmp_path / "bad.yaml"
    bad.write_text("id: x\nauthorized: false\nservers: {slack: {command: [echo]}}\ntripwires: []\n")
    result = runner.invoke(app, ["config", "apply", "--runbook", str(rb), "--scenario", str(bad)])
    assert result.exit_code == 1
    assert json.loads(cfg.read_text())["mcpServers"]["slack"]["command"] == "npx"  # untouched
