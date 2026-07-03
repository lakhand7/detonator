"""Module 7 — scenario/target discovery for `detonate list` (DESIGN.md §11)."""
from typer.testing import CliRunner

from detonator.cli import app
from detonator.inventory import find_scenarios, find_targets

runner = CliRunner()


def test_find_scenarios_returns_sorted_yaml(tmp_path):
    d = tmp_path / "scenarios"
    d.mkdir()
    (d / "b.yaml").write_text("id: b")
    (d / "a.yaml").write_text("id: a")
    (d / "notes.txt").write_text("ignore me")
    assert [p.name for p in find_scenarios(d)] == ["a.yaml", "b.yaml"]


def test_find_scenarios_missing_dir_is_empty(tmp_path):
    assert find_scenarios(tmp_path / "nope") == []


def test_find_targets_are_dirs_with_a_runbook(tmp_path):
    root = tmp_path / "targets"
    (root / "slack-ops-agent").mkdir(parents=True)
    (root / "slack-ops-agent" / "RUNBOOK.md").write_text("---\n---\n")
    (root / "no-runbook").mkdir()  # not a target: no RUNBOOK.md
    found = find_targets(root)
    assert [p.parent.name for p in found] == ["slack-ops-agent"]


def test_cli_list_shows_scenarios_and_targets(tmp_path, monkeypatch):
    (tmp_path / "scenarios").mkdir()
    (tmp_path / "scenarios" / "demo.yaml").write_text("id: demo")
    (tmp_path / "targets" / "acme").mkdir(parents=True)
    (tmp_path / "targets" / "acme" / "RUNBOOK.md").write_text("---\n---\n")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "demo.yaml" in result.output
    assert "acme" in result.output
