"""`detonate` CLI — a thin shell over the core (DESIGN.md §11).

Parse args, call the core, print; emit machine-readable output where the
orchestrator consumes it. Module 1 wires `validate`; config/proxy/eval/list land
in their own modules.
"""

from pathlib import Path

import typer
from pydantic import ValidationError

from detonator.model.loader import load_scenario

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="detonate — dynamic exploitability testing for AI agents and their MCP servers.",
)


@app.callback()
def _main() -> None:
    """Root callback; keeps `detonate` a command group (validate/config/proxy/eval/list)."""


@app.command()
def validate(
    scenario: Path = typer.Argument(..., help="Path to a scenario YAML file."),
) -> None:
    """Load + safety-bounds gate a scenario (§4). Exit 0 pass / 1 fail."""
    try:
        s = load_scenario(scenario)
    except FileNotFoundError:
        typer.echo(f"INVALID {scenario}: file not found", err=True)
        raise typer.Exit(code=1)
    except (ValidationError, ValueError, OSError) as e:
        typer.echo(f"INVALID {scenario}:\n{e}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"OK {scenario} (id={s.id})")


if __name__ == "__main__":
    app()
