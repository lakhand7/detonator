# stdin/stdout & MCP — a primer (as used in detonator)

**One line:** stdio is a dumb byte pipe; MCP is just an agreement about what bytes to send over it.

## Three streams

Every process starts with three file descriptors — plain byte streams:

| fd | name | direction |
|----|------|-----------|
| 0 | **stdin** | bytes in |
| 1 | **stdout** | bytes out (data) |
| 2 | **stderr** | bytes out (diagnostics) |

The stdout/stderr split lets a program emit *data* on stdout and *noise* on stderr without mixing.
detonator sends its `proxy: wrote …/log.jsonl` line to **stderr** and keeps **stdout** pristine.

## Pipes & EOF

A **pipe** is a one-way byte channel with a *write* end and a *read* end, usually in two processes
(`A | B` wires A's stdout → B's stdin). `subprocess.Popen(..., stdin=PIPE)` and
`asyncio.create_subprocess_exec(..., stdin=PIPE)` create them; the two processes hold opposite ends.

**EOF is the shutdown signal:** when *all* write ends of a pipe close, the reader gets end-of-stream.
detonator's whole teardown is this rule cascaded down the process tree — target exits → proxy's stdin
EOFs → proxy closes the upstream's stdin → upstream exits → proxy's read loop ends → `log.jsonl` flushed.

## Where the proxy sits (two pipes, four ends)

```
request  path:  client ─►  proxy stdin  (_client_in)  ─c2s─►  [proxy]  ─to_server─►  upstream stdin  (proc.stdin)
response path:  client ◄─  proxy stdout (_client_out) ◄to_client─ [proxy] ◄─s2c─  upstream stdout (proc.stdout)
```

- The proxy's **own** fd0/fd1 face the client. They aren't async by default, so `_wrap_stdio()` wraps
  them into asyncio streams (`_client_in` / `_client_out`).
- The **upstream's** fd0/fd1 arrive async-wrapped for free as `proc.stdin` / `proc.stdout`.
- Both pipes carry traffic independently → two concurrent pumps: `asyncio.gather(_pump_c2s, _pump_s2c)`.

## MCP over stdio

MCP's stdio transport: **the client launches the server as a subprocess and they talk over its
stdin/stdout.** The agreement is tiny:

- **Format:** JSON-RPC 2.0, **newline-delimited** — one JSON object per line, UTF-8, `\n`-terminated,
  no embedded newlines. (Hence `.jsonl`, `readline`, and `json.dumps(m) + "\n"` throughout.)
- **Direction:** requests on the server's **stdin**; responses on its **stdout**.
- **stderr is out-of-band:** the server MAY log to stderr; it MUST NOT put non-protocol bytes on
  stdout; the client MUST NOT put non-protocol bytes on the server's stdin.

So an MCP stdio server is just: *read a JSON-RPC line from stdin → work → write a JSON-RPC line to
stdout.* `tests/_fake_upstream.py` is exactly that.

## Why this makes detonator work

Because an MCP stdio server is "a command that speaks JSON-RPC over stdin/stdout," we impersonate one:
`config apply` rewrites the target's server `command` to `detonate proxy`. The client launches us, we
speak the identical protocol back, and relay byte-for-byte (except the one poisoned message) to the
real server we spawned. **Config edit + stdio = the entire mechanism — no interception hooks** (§2).

## Gotchas (all consequences of the above)

- **stdout is sacred** — any stray write desyncs the JSON-RPC stream. Diagnostics go to stderr; the
  proxy forwards original bytes verbatim except the single injected line.
- **EOF is the only shutdown protocol** — and the proxy must *actively* close the upstream's stdin
  mid-shutdown, or `_pump_s2c` waits forever and the proxy deadlocks.
- **Blocking reads force async** — a full-duplex relay needs both directions readable at once, which
  is the whole reason for `_wrap_stdio()` + two pumps.
- **Newline framing** — no message may contain a raw `\n`; JSON string-escaping guarantees it.
