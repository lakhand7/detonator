"""`detonate` CLI — a thin shell over the core (DESIGN.md §11).

Parse args, call the core, print; emit machine-readable output where the
orchestrator consumes it. Module 1 wires `validate`; config/proxy/eval/list land
in their own modules.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from pydantic import ValidationError

from detonator.model.loader import load_scenario
from detonator.model.scenario import Scenario, ServerSpec
from detonator.proxy import get as get_transport
from detonator.proxy.log import MessageLog, resolve_run_dir
from detonator.proxy.session import ProxySession
from detonator.eval.run import evaluate, load_log, load_run_scenario

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


def _select_server(scenario: Scenario, server: Optional[str]) -> ServerSpec:
    """Pick the upstream server: by --server name, or the sole entry; fail closed otherwise."""
    servers = scenario.servers
    if server is not None:
        if server not in servers:
            raise typer.BadParameter(
                f"server {server!r} not in scenario.servers ({list(servers)})"
            )
        return servers[server]
    if len(servers) == 1:
        return next(iter(servers.values()))
    raise typer.BadParameter(
        f"scenario has {len(servers)} servers; pass --server (one of {list(servers)})"
    )


async def _run_session(transport, inject, log: MessageLog) -> None:
    await transport.start()
    try:
        await ProxySession(transport, inject, log).run()
    finally:
        await transport.aclose()
        log.close()


@app.command()
def proxy(
    scenario: Path = typer.Option(..., "--scenario", help="Scenario YAML."),
    server: Optional[str] = typer.Option(None, "--server", help="Which scenario.servers entry to front."),
    record: bool = typer.Option(False, "--record", help="Force passthrough: ignore inject (record mode)."),
    run_dir: Optional[Path] = typer.Option(
        None, "--run-dir", help="Run dir (else $DETONATE_RUN_DIR, else runs/<UTC-ts>)."
    ),
) -> None:
    """Run AS the target's MCP server over stdio: spawn upstream, relay, poison one message, log (§8, §11).

    stdout is the client channel — only relayed JSON-RPC goes there; all diagnostics go to stderr.
    """
    try:
        scenario_obj = load_scenario(scenario)
    except (ValidationError, ValueError, OSError) as e:
        typer.echo(f"proxy: invalid scenario {scenario}:\n{e}", err=True)
        raise typer.Exit(code=1)
    spec = _select_server(scenario_obj, server)
    inject = None if record else scenario_obj.inject
    rd = resolve_run_dir(str(run_dir) if run_dir else None)
    # Save the scenario alongside the log so `detonate eval <run-dir>` is self-contained (§8).
    (rd / "scenario.json").write_text(scenario_obj.model_dump_json(indent=2))
    log = MessageLog(rd / "log.jsonl")
    transport = get_transport("stdio")(spec)
    asyncio.run(_run_session(transport, inject, log))
    typer.echo(f"proxy: wrote {rd / 'log.jsonl'} ({len(log.messages)} messages)", err=True)


@app.command("eval")
def eval_cmd(
    run_dir: Optional[Path] = typer.Argument(
        None, help="Run directory (contains log.jsonl + scenario.json)."
    ),
    replay: Optional[Path] = typer.Option(
        None, "--replay", help="Evaluate a bare log.jsonl instead of a run dir."
    ),
    scenario: Optional[Path] = typer.Option(
        None, "--scenario", help="Scenario for --replay (or to override the run dir's copy)."
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit the Verdict as JSON."),
) -> None:
    """Pure `evaluate` over the log; writes report.json when given a run dir (§5, §11)."""
    if replay is not None:
        log_path = replay
    elif run_dir is not None:
        log_path = run_dir / "log.jsonl"
    else:
        typer.echo("eval: pass a run directory or --replay <log.jsonl>", err=True)
        raise typer.Exit(code=2)

    try:
        if scenario is not None:
            scen = load_scenario(scenario)
        else:
            beside = log_path.parent / "scenario.json"
            if not beside.exists():
                typer.echo(
                    "eval: no scenario — pass --scenario or eval a run dir with scenario.json",
                    err=True,
                )
                raise typer.Exit(code=2)
            scen = load_run_scenario(beside)
        log = load_log(log_path)
    except (FileNotFoundError, OSError, ValueError, ValidationError) as e:
        typer.echo(f"eval: {e}", err=True)
        raise typer.Exit(code=2)

    verdict = evaluate(scen, log, str(log_path))
    if run_dir is not None:
        (run_dir / "report.json").write_text(verdict.model_dump_json(indent=2))

    if json_out:
        typer.echo(verdict.model_dump_json())
    else:
        typer.echo(verdict.status)
        for r in verdict.results:
            typer.echo(f"  [{'FIRED' if r.fired else '----'}] {r.type}")
            for ev in r.evidence:
                typer.echo(f"      - {ev}")
        if verdict.repro:
            typer.echo(f"  repro: {verdict.repro}")


def proxy_main() -> None:
    """Console-script alias `detonate-mcp-proxy` -> `detonate proxy` (§11, §15)."""
    sys.argv = [sys.argv[0], "proxy", *sys.argv[1:]]
    app()


if __name__ == "__main__":
    app()
