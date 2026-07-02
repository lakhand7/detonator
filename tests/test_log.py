"""Module 2 — MessageLog jsonl output + run-directory resolution (DESIGN.md §8)."""
import json
from pathlib import Path

from detonator.proxy.log import MessageLog, resolve_run_dir


def test_message_log_writes_one_loggedmessage_per_line(tmp_path):
    path = tmp_path / "log.jsonl"
    with MessageLog(path) as log:
        log.append("c2s", {"jsonrpc": "2.0", "id": 7, "method": "tools/call"})
        log.append("s2c", {"jsonrpc": "2.0", "id": 7, "result": {"isError": False}}, poisoned=True)
    lines = path.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {
        "i": 0,
        "dir": "c2s",
        "raw": {"jsonrpc": "2.0", "id": 7, "method": "tools/call"},
        "poisoned": False,
    }
    second = json.loads(lines[1])
    assert second["i"] == 1 and second["dir"] == "s2c" and second["poisoned"] is True


def test_run_dir_explicit_beats_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DETONATE_RUN_DIR", "runs/from-env")  # must be ignored
    d = resolve_run_dir(str(tmp_path / "explicit"))
    assert d == (tmp_path / "explicit")
    assert d.is_dir()
    assert (tmp_path / "runs" / "latest").resolve() == d.resolve()


def test_run_dir_from_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DETONATE_RUN_DIR", "runs/rec")
    d = resolve_run_dir(None)
    assert d == Path("runs/rec")
    assert d.is_dir()
    assert (tmp_path / "runs" / "latest").resolve() == d.resolve()


def test_run_dir_default_is_timestamp_under_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DETONATE_RUN_DIR", raising=False)
    d = resolve_run_dir(None)
    assert d.parent == Path("runs")
    assert d.is_dir()
    assert (tmp_path / "runs" / "latest").resolve() == d.resolve()
