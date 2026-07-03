"""Discovery for `detonate list` (DESIGN.md §11): scenarios and targets in the tree."""

from pathlib import Path


def find_scenarios(root: str | Path = "scenarios") -> list[Path]:
    root = Path(root)
    return sorted(root.glob("*.yaml")) if root.is_dir() else []


def find_targets(root: str | Path = "targets") -> list[Path]:
    """A target is a subdirectory containing a RUNBOOK.md."""
    root = Path(root)
    return sorted(root.glob("*/RUNBOOK.md")) if root.is_dir() else []
