---
# Target runbook front-matter (DESIGN.md §12). Our code executes these commands; nothing
# about the target is hard-coded. Fill in the fields below, then write prose beneath.
#
#   launch:           OPTIONAL — start a long-running target (servers). Omit for one-shot CLIs.
#   trigger:          REQUIRED — synchronous command that runs the benign task. May embed {task}.
#                     MUST exit only when the task has fully completed (completion contract below).
#   task:             the benign task prompt text substituted into {trigger} as {task}.
#   wait:             OPTIONAL — command run after `trigger` that BLOCKS until the task is done.
#   mcp_config_path:  path to the target's MCP config file the proxy entry is injected into.
#   mcp_server_name:  the server key in that config to replace (e.g. "slack").
#   stop:             OPTIONAL — teardown command.
#   observe:          OPTIONAL — path/glob where the target writes its own logs (advisory only).

launch:
trigger: '<REQUIRED: synchronous command that runs the benign task; may use {task}>'
task: '<the benign task prompt>'
wait:
mcp_config_path: <path to the target MCP config, e.g. ./.mcp.json>
mcp_server_name: <server key to replace, e.g. slack>
stop:
observe:
---

# <Target name> runbook

Describe the target: what it is, how to set it up, and any operator notes. Secrets
(tokens, keys) live in the **environment** and are expanded from `ServerSpec.env` `${VAR}`
at spawn — never written into scenario files (§15).

## Completion contract (critical, §12)

`trigger` MUST be a foreground, **synchronous** command that exits only when the benign task
has fully completed. The orchestrator treats `trigger`'s exit (then `wait`, if present) as
"the run is done" and immediately calls `detonate eval`. Because the target launches the proxy
as its MCP-server subprocess, the target exiting closes the proxy's stdin (EOF), which flushes
`log.jsonl` — so a synchronous `trigger` guarantees a complete log before `eval`. A target that
keeps working in the background races an incomplete log and can report a **false UNREACHABLE**.

- **One-shot CLI targets:** `trigger` runs the task and exits — naturally synchronous.
- **Long-running server targets:** wrap launch → send task → wait-for-done → shutdown into one
  blocking `trigger`, or provide a `wait` command that blocks until the task is complete.
