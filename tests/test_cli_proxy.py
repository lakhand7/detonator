"""Module 2 — server selection for `detonate proxy` (DESIGN.md §11 --server).

V1 scenarios carry exactly one server, but --server picks it by name; the selection
logic (default-the-single, pick-by-name, fail-closed on missing/ambiguous) is the one
testable bit of the otherwise-imperative proxy command.
"""
import pytest
import typer

from detonator.cli import _select_server
from detonator.model.scenario import Scenario


def _scn(servers):
    return Scenario(
        id="x",
        authorized=True,
        servers=servers,
        inject=None,
        allow=["t"],
        tripwires=[{"type": "unauthorized_tool"}],
    )


def test_selects_single_server_when_no_name_given():
    s = _scn({"slack": {"command": ["echo", "up"]}})
    assert _select_server(s, None).command == ["echo", "up"]


def test_selects_named_server():
    s = _scn({"slack": {"command": ["a"]}, "gh": {"command": ["b"]}})
    assert _select_server(s, "gh").command == ["b"]


def test_missing_named_server_fails_closed():
    s = _scn({"slack": {"command": ["a"]}})
    with pytest.raises(typer.BadParameter):
        _select_server(s, "nope")


def test_ambiguous_without_name_fails_closed():
    s = _scn({"slack": {"command": ["a"]}, "gh": {"command": ["b"]}})
    with pytest.raises(typer.BadParameter):
        _select_server(s, None)
