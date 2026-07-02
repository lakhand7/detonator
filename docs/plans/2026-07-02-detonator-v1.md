# detonator V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Execution model (user-directed):** Implement ONE module at a time. After each module, stop and request human review. Commit only after the user approves, then advance to the next module.

**Goal:** Build `detonate` — a config-based, byte-faithful stdio MCP proxy that poisons exactly one tool message and logs every JSON-RPC message, plus a deterministic evaluator that renders a binary REACHABLE/UNREACHABLE verdict over that log, plus a Claude Code orchestrator skill that drives the red-team loop.

**Architecture:** Pure functional core (inject transforms + tripwire evaluator are pure functions over value objects), imperative shell (the async proxy session + CLI). Three uniform seams — Transport, InjectTransform, Tripwire — each Protocol + module registry + `@register` decorator. Config is pydantic v2 at the boundary (YAML in, validated, safety-gated); everything through the core is frozen value objects that serialize to `report.json`.

**Tech Stack:** Python ≥3.11, pydantic v2, Typer, PyYAML, asyncio (stdlib), pytest. Node.js only for the live Slack demo upstream — never for the hermetic tests.

**Source of truth:** `DESIGN.md` in repo root. Section references (§N) below point into it. Obey §19 non-goals strictly; everything outside §18 V1 scope is deferred.

---

## File Structure (target end-state)

```
pyproject.toml            # packaging + console_scripts + pytest config
README.md                 # module 7
LICENSE                   # MIT, module 7
src/detonator/
  __init__.py
  cli.py                  # Typer app: validate / config / proxy / eval / list (thin shell, emits JSON)
  model/
    __init__.py
    scenario.py           # ServerSpec, Inject, TripwireSpec union, Scenario (+safety validator)  [M1]
    wire.py               # LoggedMessage, ToolCall, tool_calls()                                  [M1]
    context.py            # EvidenceContext                                                         [M1]
    verdict.py            # TripwireResult, Verdict                                                 [M1]
    loader.py             # load_scenario(path) -> Scenario (YAML -> pydantic)                      [M1]
  proxy/
    __init__.py           # imports transport submodules so registry populates                     [M2]
    transport.py          # Transport Protocol + registry (register/get)                           [M2]
    stdio.py              # @register("stdio") StdioTransport                                       [M2]
    session.py            # ProxySession (humble object; two async pumps)                           [M2]
    log.py                # MessageLog (append + jsonl flush) + run-dir resolution                  [M2]
  poison/
    __init__.py           # imports strategy submodules                                             [M3]
    strategy.py           # InjectTransform Protocol + registry                                     [M3]
    match.py              # should_poison(raw, tool, inject) -> bool (pure, §9 matcher)             [M3]
    splice.py             # @register("splice") SpliceIntoResult (§9)                               [M3]
    description.py        # @register("description") RewriteDescription (§9)                        [M3]
  eval/
    __init__.py           # imports tripwire submodules                                             [M4]
    tripwire.py           # Tripwire Protocol + registry                                            [M4]
    canary_exfil.py       # @register("canary_exfil") (§10)                                         [M4]
    unauthorized_tool.py  # @register("unauthorized_tool") (§10)                                    [M4]
    run.py                # verdict_from(), evaluate(), load_log(run_dir|replay)                    [M4]
orchestrator/
  SKILL.md                # Claude Code skill manifest                                              [M6]
  RED-TEAM.md             # the §13 loop playbook                                                   [M6]
targets/
  RUNBOOK.template.md     # §12 fields                                                              [M6]
  slack-ops-agent/RUNBOOK.md                                                                        [M7]
scenarios/
  slack-ops-indirect-injection.yaml                                                                 [M7]
fixtures/
  slack_exploit.jsonl     # golden POSITIVE -> REACHABLE                                            [M5]
  slack_clean.jsonl       # golden NEGATIVE -> UNREACHABLE                                          [M5]
tests/
  test_validate.py [M1]  test_session.py [M2]  test_transform.py [M3]
  test_tripwires.py [M4]  test_replay.py [M5]
.github/workflows/ci.yml  # module 5
```

Deferred kinds are stubbed behind seams only when we reach them; do NOT create `http_sse`, `overwrite`, `egress`, etc. in V1 (§19/§20).

---

## Module → Task map (review checkpoint after each)

| Module | Design | Definition of Done | Test file |
|---|---|---|---|
| 1 | D1 | `detonate validate` accepts a good scenario, rejects each bad case | `test_validate.py` |
| 2 | D2 | `ProxySession` relays byte-faithfully; `log.jsonl` has full round-trip | `test_session.py` |
| 3 | D3 | poison scenario ⇒ target result `poisoned:true` and still valid JSON | `test_transform.py` |
| 4 | D4 | poisoned run ⇒ REACHABLE with repro; `report.json` written | `test_tripwires.py` |
| 5 | D5 | `--replay` fixtures ⇒ REACHABLE / UNREACHABLE in a clean env | `test_replay.py` |
| 6 | D6 | orchestrator skill drives the §14 loop; verdict only from `eval` | — |
| 7 | D7 | fresh clone: pip install, hermetic tests, live Slack REACHABLE | — |

---

## Task 1: Schemas + validate (Module 1 — CURRENT)

**Files:**
- Create: `pyproject.toml`
- Create: `src/detonator/__init__.py`, `src/detonator/model/__init__.py`
- Create: `src/detonator/model/scenario.py`, `wire.py`, `context.py`, `verdict.py`, `loader.py`
- Create: `src/detonator/cli.py` (skeleton: `validate` command wired; `config`/`proxy`/`eval`/`list` stubs that raise "not implemented in this module")
- Create: `tests/test_validate.py`, `tests/conftest.py` (fixtures dir helpers if needed)
- Create: `scenarios/slack-ops-indirect-injection.yaml` (minimal valid scenario for the happy-path test)

**Schemas are transcribed verbatim from DESIGN.md §4** (frozen value objects use `ConfigDict(frozen=True)`; config DTOs use the safety `model_validator`). The one intentional deviation from a naive reading: nothing — match §4 exactly.

- [ ] **Step 1 — Write failing tests** (`tests/test_validate.py`): a valid scenario loads; `authorized:false` raises; a `canary_exfil` canary absent from `inject.payload` raises; `unauthorized_tool` with empty `allow` raises. Assert on `load_scenario(path)` / `Scenario(**dict)`.
- [ ] **Step 2 — Run tests, verify they fail** (`ImportError`/`ModuleNotFoundError`).
- [ ] **Step 3 — Implement `model/scenario.py`** (ServerSpec, Inject, CanaryExfilSpec, UnauthorizedToolSpec, TripwireSpec discriminated union, Scenario + `_safety_bounds` model_validator) per §4.
- [ ] **Step 4 — Implement `model/wire.py`, `context.py`, `verdict.py`** (frozen models + `tool_calls()` projection) per §4.
- [ ] **Step 5 — Implement `model/loader.py`** (`load_scenario(path)` reads YAML, constructs `Scenario`, surfaces `ValidationError` clearly).
- [ ] **Step 6 — Implement `cli.py`** Typer app with `validate` (exit 0 pass / 1 fail, errors to stderr) and stub subcommands; add `if __name__ == "__main__": app()`.
- [ ] **Step 7 — Run `pytest`, verify green.**
- [ ] **Step 8 — Manual CLI check:** `validate` returns exit 0 on the good scenario, exit 1 + stderr on a bad one.
- [ ] **Step 9 — Request human review. On approval: commit** `feat: module 1 — schemas + validate`.

**Validation rules (from §4 `_safety_bounds`):**
- `authorized` must be `true`, else `ValueError`.
- for each `CanaryExfilSpec`, if `inject` present, every value must be a substring of `inject.payload`.
- for each `UnauthorizedToolSpec`, `allow` must be non-empty.

## Task 2: Transport + proxy record mode (Module 2)
Transport Protocol + registry + `StdioTransport` (spawns `ServerSpec.command`, newline-delimited JSON, `${VAR}` env expansion); `ProxySession` (§6: two async pumps, `id→tool` correlation, forward ORIGINAL bytes); `MessageLog` (append + jsonl); run-dir resolution `--run-dir > $DETONATE_RUN_DIR > runs/<UTC-ISO>/` + `runs/latest` symlink (§8); `detonate proxy --record`. Test with a **FakeTransport** yielding canned bytes (§17). Detailed TDD steps authored when this module starts.

## Task 3: Poison strategies (Module 3)
InjectTransform Protocol + registry; `should_poison` matcher (§9); `splice` (structure-aware, append-text-block fallback) + `description` (append) per §9; wire `get(strategy).apply` into `ProxySession._pump_s2c`. Pure-function unit tests with literals (§17). Detailed steps at module start.

## Task 4: Tripwires + eval (Module 4)
Tripwire Protocol + registry; `EvidenceContext{mcp_log}`; `canary_exfil` + `unauthorized_tool` (§10); `verdict_from`/`evaluate` (§5); `detonate eval <run-dir>|--replay [--json]` writes `report.json`. Detailed steps at module start.

## Task 5: Replay + hermetic CI (Module 5)
Hand-author `fixtures/slack_exploit.jsonl` (REACHABLE) + `slack_clean.jsonl` (UNREACHABLE); `--replay` path; GitHub Actions CI running all tests with no Node/token. Detailed steps at module start.

## Task 6: Orchestrator skill (Module 6)
`orchestrator/SKILL.md` + `RED-TEAM.md` (§13 loop, verdict only from `eval`); `detonate config` (print entry) + `config apply`/`config restore` (idempotent backup, §11); `targets/RUNBOOK.template.md` (§12). Uses superpowers:writing-skills. Detailed steps at module start.

## Task 7: Worked example + docs + release (Module 7)
`scenarios/slack-ops-indirect-injection.yaml` (final) + `targets/slack-ops-agent/RUNBOOK.md`; `detonate list`; README; MIT LICENSE; tag v0.1. Detailed steps at module start.

---

## Conventions
- **DRY / YAGNI / TDD / frequent commits** — but commits gated on human review per the execution model above.
- Exact `file_path:line` references when modifying.
- Do not implement deferred kinds (§19/§20). When a seam is added, only V1 kinds register.
- The proxy forwards bytes unchanged except the single injected message (§7). When in doubt, relay verbatim.
```
