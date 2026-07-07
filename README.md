# detonator

[![CI](https://github.com/lakhand7/detonator/actions/workflows/ci.yml/badge.svg)](https://github.com/lakhand7/detonator/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

**Dynamic exploitability testing for AI agents and the MCP servers they use.**

Static AI/MCP scanners answer *"could this be dangerous?"* — high recall, high false positives.
detonator answers the harder, more useful question: **given an agent and its tools, does a specific
adversarial input actually make it take a harmful action?** — and proves the answer with a captured,
replayable trace.

Two earned verdicts:

- **REACHABLE** — a tripwire fired; the exploit is proven, with a minimal repro.
- **UNREACHABLE** — the adversarial condition ran and nothing fired; evidence the flagged risk does
  not fire in this configuration.

## How it works

detonator hands the agent an MCP server entry that points at **`detonate proxy`** instead of the real
server — the agent connects to us *because its own config says so* (config-based, not interception-based).
The proxy is a byte-faithful stdio relay that **poisons exactly one tool message** and **logs every
JSON-RPC message**. A deterministic evaluator then scans that log:

```
 TARGET (any agent + runbook)
   │  benign task fires MCP tool calls
   ▼
 detonate proxy   ──  relays to the real MCP server, poisons one message, logs everything
   │
   ▼
 detonate eval    ──  deterministic tripwires over the log  ──►  REACHABLE / UNREACHABLE  (the verdict of record)
```

The verdict is authored by pure code (`detonate eval`), never by the orchestrator — *judge out of the jury*.

## Install

```bash
git clone https://github.com/lakhand7/detonator.git
cd detonator
uv venv && uv pip install -e ".[dev]"   # or: pip install -e ".[dev]"
```

Requires Python ≥ 3.11. Node.js is needed **only** to run the live Slack example upstream — not for
detonator itself and not for the tests.

## Quickstart (hermetic — no Node, no tokens)

Run the test suite, then reproduce the headline result — *the same poisoned input yields opposite
verdicts* — straight from the golden fixtures:

```bash
pytest -q

# agent OBEYED the injection -> the canary was exfiltrated -> REACHABLE
detonate eval --replay fixtures/slack_exploit.jsonl --scenario scenarios/slack-ops-indirect-injection.yaml

# agent IGNORED it -> no canary in any downstream call -> UNREACHABLE
detonate eval --replay fixtures/slack_clean.jsonl   --scenario scenarios/slack-ops-indirect-injection.yaml
```

Both fixtures carry a **byte-identical** poisoned `conversations_history` result; they differ only in
whether the agent acted on it. Same input, opposite verdicts, proven by a log scan.

## The worked example: a Slack ops agent (live)

Point detonator at a real "summarize #incidents, post a recap to #ops-summary" agent wired to the Slack
MCP server. Bring your own agent + `SLACK_BOT_TOKEN`; detonator hard-codes nothing about it. The target
is described entirely by a **runbook** (`targets/slack-ops-agent/RUNBOOK.md`), and the attack by a
**scenario** (`scenarios/slack-ops-indirect-injection.yaml`). See the runbook for the exact commands.

## Point *any* MCP agent at it

There's no target-specific code in this repo. To test your own agent, write a runbook (copy
`targets/RUNBOOK.template.md`) with a handful of fields:

- `mcp_config_path` / `mcp_server_name` — where its MCP config is and which server to front.
- `trigger` (+ optional `launch`/`wait`/`stop`) + `task` — how to run the benign task **synchronously**
  (it must exit only when the task is truly done — see the completion contract in §12 of `DESIGN.md`).

## CLI

| Command | Purpose |
|---|---|
| `detonate validate <scenario>` | load + safety-gate a scenario (exit 0 pass / 1 fail) |
| `detonate config show <scenario>` | print the MCP entry JSON to paste into a target config |
| `detonate config apply --runbook R --scenario S` | patch the target's MCP config to launch the proxy (idempotent backup) |
| `detonate config restore --runbook R` | restore the target's MCP config from backup |
| `detonate proxy --scenario S --server N` | run AS the target's MCP server (launched *by* the target) |
| `detonate eval <run-dir> \| --replay <log> [--json]` | the deterministic verdict; writes `report.json` |
| `detonate list` | list scenarios and targets in the tree |

## Repository layout

```
src/detonator/        the package
  ├─ model/           frozen value objects: scenario, wire messages, context, verdict
  ├─ proxy/           the async stdio relay — transport, session, poison-and-log
  ├─ poison/          inject transforms (splice, description) + JSON Pointer targeting
  ├─ eval/            deterministic tripwires (canary_exfil, unauthorized_tool) + runner
  ├─ inventory.py     scenario/target discovery for `detonate list`
  └─ cli.py           the `detonate` CLI
scenarios/            attack definitions (poison + tripwires), e.g. the Slack injection
targets/              runbooks describing how to launch a benign task against an agent
fixtures/             hand-authored golden JSON-RPC logs for hermetic replay tests
orchestrator/         the Claude Code red-team skill (SKILL.md + RED-TEAM.md)
tests/                hermetic suite — pure-Python fake MCP upstream, no Node/tokens
DESIGN.md             the full design spec; docs/ has supporting primers
```

## Orchestrator (Claude Code skill)

The red-team loop — *understand the real tool shape → craft a poison variant → trigger the benign task
→ read the verdict → iterate* — is a Claude Code skill (`orchestrator/SKILL.md` + `RED-TEAM.md`), not
bespoke code. It drives the `detonate` CLI and stops on the first REACHABLE (or after N variants),
reporting `exploit_rate` and the repro. The skill may read the verdict to decide whether to iterate;
it **never** authors the verdict itself.

## Architecture

Pure functional core (the inject transforms and the tripwire evaluator are pure functions over frozen
value objects) wrapped in an imperative shell (the async proxy + CLI). Three uniform growth seams, each
a Protocol + module registry + `@register` decorator:

- **Transport** — `stdio` (V1); `http_sse` deferred.
- **InjectTransform** — `splice`, `description` (V1); `overwrite`/`error`/`structured` deferred.
- **Tripwire** — `canary_exfil`, `unauthorized_tool` over the MCP log (V1); `egress`/`fs_audit`/
  `syscall`/`approval_bypass` deferred (they need the isolation tier).

See `DESIGN.md` for the full spec, and `docs/stdio-and-mcp.md` for a primer on how stdio + MCP fit together.

## Scope (V1)

In: config-based stdio proxy (record + poison), the two inject strategies, the two `mcp_log` tripwires,
the CLI, the orchestrator skill, the Slack worked example, and hermetic replay tests. Out (deferred):
containers/isolation, off-MCP exfil detection, HTTP/SSE transport, LLM adjudication, provenance/signing.
**Known V1 limitation:** the proxy log only observes harm that manifests as a proxied MCP tool call;
off-MCP exfil is invisible by design (that's the deferred `egress`/`fs_audit` tier).

## Development

```bash
uv run --no-sync pytest -q     # hermetic suite (also what CI runs, across Python 3.11–3.13)
```

## License

MIT — see [LICENSE](LICENSE).
