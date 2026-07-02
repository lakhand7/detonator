"""YAML -> validated Scenario (DESIGN.md §11 `detonate validate`).

Thin: read the file, parse YAML, hand the mapping to the pydantic Scenario. Any
safety-bounds violation surfaces as a pydantic ValidationError for the CLI to render.
"""

from pathlib import Path

import yaml

from detonator.model.scenario import Scenario


def load_scenario(path: str | Path) -> Scenario:
    """Load and safety-gate a scenario YAML file.

    Raises pydantic.ValidationError on any safety-bounds violation (§4) and
    ValueError if the file does not parse to a mapping.
    """
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError(f"scenario file {path!s} did not parse to a mapping")
    return Scenario(**data)
