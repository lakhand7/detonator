"""Module 2 — ProxySession record-mode relay + id->tool correlation (DESIGN.md §6, §17).

Record mode (inject=None) makes the session a transparent relay: forward the ORIGINAL
bytes in both directions, log every message unpoisoned, and maintain the id->tool
correlation map that poison mode (Module 3) will consume.
"""
import asyncio

from detonator.proxy.session import ProxySession

from fakes import FakeTransport, RecordingLog, jline

CALL = {
    "jsonrpc": "2.0",
    "id": 7,
    "method": "tools/call",
    "params": {"name": "conversations_history", "arguments": {"channel": "#incidents"}},
}
RESULT = {
    "jsonrpc": "2.0",
    "id": 7,
    "result": {"content": [{"type": "text", "text": "[]"}], "isError": False},
}


def _run(session):
    asyncio.run(session.run())


def test_record_mode_forwards_bytes_verbatim():
    c2s, s2c = [jline(CALL)], [jline(RESULT)]
    t = FakeTransport(c2s, s2c)
    _run(ProxySession(t, None, RecordingLog()))
    assert t.to_server_calls == c2s  # client->server bytes unchanged
    assert t.to_client_calls == s2c  # server->client bytes unchanged


def test_record_mode_logs_both_directions_unpoisoned():
    log = RecordingLog()
    _run(ProxySession(FakeTransport([jline(CALL)], [jline(RESULT)]), None, log))
    c2s_entries = [e for e in log.entries if e[0] == "c2s"]
    s2c_entries = [e for e in log.entries if e[0] == "s2c"]
    assert len(c2s_entries) == 1 and c2s_entries[0][1]["method"] == "tools/call"
    assert len(s2c_entries) == 1 and s2c_entries[0][1]["result"]["isError"] is False
    assert all(entry[2] is False for entry in log.entries)  # record mode poisons nothing


def test_correlation_map_populated_on_tools_call():
    session = ProxySession(FakeTransport([jline(CALL)], []), None, RecordingLog())
    asyncio.run(session._pump_c2s())
    assert session._pending == {7: "conversations_history"}


def test_correlation_map_consumed_on_matching_result():
    session = ProxySession(FakeTransport([jline(CALL)], [jline(RESULT)]), None, RecordingLog())
    _run(session)
    assert session._pending == {}  # popped when its matching result came back


def test_non_tools_call_request_not_correlated():
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    session = ProxySession(FakeTransport([jline(init)], []), None, RecordingLog())
    asyncio.run(session._pump_c2s())
    assert session._pending == {}


def test_notifications_without_id_pass_through():
    # notifications carry no id and no result; the session must not choke on the missing id.
    note_c2s = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    note_s2c = {"jsonrpc": "2.0", "method": "notifications/message", "params": {"level": "info"}}
    t = FakeTransport([jline(note_c2s)], [jline(note_s2c)])
    log = RecordingLog()
    _run(ProxySession(t, None, log))
    assert t.to_server_calls == [jline(note_c2s)]
    assert t.to_client_calls == [jline(note_s2c)]
    assert len(log.entries) == 2
