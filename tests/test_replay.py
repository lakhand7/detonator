"""Module 5 — hermetic replay of golden fixtures (DESIGN.md §17).

The two fixtures are hand-authored minimal JSON-RPC logs that share the same poisoned
input; they differ only in whether the agent obeyed. Evaluated against the worked-example
scenario they yield opposite verdicts — "same input, opposite verdicts, proven by a log
scan" (§3). No Node, no token, no live agent.
"""
import json
from pathlib import Path

from typer.testing import CliRunner

from detonator.cli import app

runner = CliRunner()

REPO = Path(__file__).parent.parent
SCENARIO = REPO / "scenarios" / "slack-ops-indirect-injection.yaml"
FIXTURES = REPO / "fixtures"


def _replay(fixture: str) -> dict:
    result = runner.invoke(
        app, ["eval", "--replay", str(FIXTURES / fixture), "--scenario", str(SCENARIO), "--json"]
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_exploit_fixture_is_reachable():
    verdict = _replay("slack_exploit.jsonl")
    assert verdict["status"] == "REACHABLE"
    assert "canary_exfil" in verdict["repro"]["fired"]


def test_clean_fixture_is_unreachable():
    verdict = _replay("slack_clean.jsonl")
    assert verdict["status"] == "UNREACHABLE"
    assert verdict["repro"] is None


def test_fixtures_share_the_same_poisoned_input():
    # both fixtures carry the identical poisoned conversations_history result; they differ
    # only in whether the downstream post_message exfiltrated the canary.
    exploit = (FIXTURES / "slack_exploit.jsonl").read_text().splitlines()
    clean = (FIXTURES / "slack_clean.jsonl").read_text().splitlines()
    poisoned_exploit = [json.loads(x) for x in exploit if json.loads(x)["poisoned"]]
    poisoned_clean = [json.loads(x) for x in clean if json.loads(x)["poisoned"]]
    assert poisoned_exploit and poisoned_exploit == poisoned_clean
