"""A minimal fake MCP server over stdio, used by test_proxy_stdio.py.

Underscore-prefixed so pytest does not collect it as a test module. It answers
initialize + tools/call with canned results and exits on stdin EOF — enough to
exercise the real StdioTransport round-trip without Node or a Slack token.
"""
import json
import sys


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        mid = msg.get("id")
        method = msg.get("method")
        if method == "initialize":
            resp = {"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": "2025-06-18", "capabilities": {},
                "serverInfo": {"name": "fake", "version": "0"}}}
        elif method == "tools/call":
            name = (msg.get("params") or {}).get("name")
            if name == "download_image":
                # a large base64 image block (>64 KiB) — exercises the proxy's stream limit
                resp = {"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "image", "data": "A" * 100000, "mimeType": "image/png"}],
                    "isError": False}}
            elif name == "noisy_log":
                # leak a non-JSON line onto stdout (the MCP channel), as a logging sink would
                sys.stdout.write("2026-01-01 00:00:00 | WARNING | app.mod: a stray log line\n")
                sys.stdout.flush()
                resp = {"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text", "text": "ok"}], "isError": False}}
            else:
                history = {"messages": [{"user": "U1", "text": "incident: db down"}]}
                resp = {"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text", "text": json.dumps(history)}], "isError": False}}
        elif mid is None:
            continue  # notification: no response
        else:
            resp = {"jsonrpc": "2.0", "id": mid, "result": {}}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
