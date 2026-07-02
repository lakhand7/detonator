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
