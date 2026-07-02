"""Module 3 — inject transforms + matcher, the "must be correct" pure functions (§9, §17).

These are exercised with literals and hand-authored fixtures — no live agent, no proxy,
no network. Every splice output MUST round-trip as valid JSON and remain a valid MCP
result; the append-text-block fallback guarantees that for any shape.
"""
import json

from detonator.model.scenario import Inject
from detonator.poison.match import should_poison
from detonator.poison.splice import SpliceIntoResult
from detonator.poison.description import RewriteDescription

splice = SpliceIntoResult()


def _inject(**kw) -> Inject:
    base = {"tool": "conversations_history", "payload": "P"}
    base.update(kw)
    return Inject(**base)


def _result_text(text: str) -> dict:
    return {"jsonrpc": "2.0", "id": 7,
            "result": {"content": [{"type": "text", "text": text}], "isError": False}}


# --- should_poison (matcher, §9) -----------------------------------------

def test_should_poison_result_requires_result_and_correlated_tool():
    inj = _inject(where="result", tool="conversations_history")
    assert should_poison(_result_text("[]"), "conversations_history", inj) is True


def test_should_poison_result_false_for_other_tool():
    inj = _inject(where="result", tool="conversations_history")
    assert should_poison(_result_text("[]"), "post_message", inj) is False


def test_should_poison_result_false_without_result_key():
    inj = _inject(where="result", tool="conversations_history")
    req = {"jsonrpc": "2.0", "id": 7, "method": "tools/call"}
    assert should_poison(req, "conversations_history", inj) is False


def test_should_poison_description_matches_tool_in_tools_list_no_correlation():
    inj = _inject(where="description", tool="conversations_history")
    raw = {"result": {"tools": [{"name": "post_message"}, {"name": "conversations_history"}]}}
    assert should_poison(raw, None, inj) is True


def test_should_poison_description_false_when_tool_absent():
    inj = _inject(where="description", tool="conversations_history")
    raw = {"result": {"tools": [{"name": "post_message"}]}}
    assert should_poison(raw, None, inj) is False


# --- splice (where=result, §9) -------------------------------------------

def test_splice_into_json_array_appends_native_looking_message():
    raw = _result_text(json.dumps([{"user": "U1", "text": "hi"}]))
    out = splice.apply(raw, "CANARY-123")
    arr = json.loads(out["result"]["content"][0]["text"])  # still valid JSON
    assert len(arr) == 2
    assert arr[-1]["text"] == "CANARY-123"  # payload placed in the text-like field
    assert arr[-1]["user"] == "U1"          # shaped like its sibling (native-looking)
    json.dumps(out)                          # whole result round-trips


def test_splice_into_json_dict_with_list_value():
    raw = _result_text(json.dumps({"ok": True, "messages": [{"text": "a"}]}))
    out = splice.apply(raw, "CANARY-123")
    parsed = json.loads(out["result"]["content"][0]["text"])
    assert parsed["messages"][-1]["text"] == "CANARY-123"
    assert len(parsed["messages"]) == 2
    assert parsed["ok"] is True


def test_splice_empty_array_still_carries_payload():
    raw = _result_text("[]")
    out = splice.apply(raw, "CANARY-123")
    assert json.loads(out["result"]["content"][0]["text"]) == [{"text": "CANARY-123"}]


def test_splice_into_plaintext_appends_extra_text_block():
    raw = _result_text("just prose, not JSON")
    out = splice.apply(raw, "CANARY-123")
    content = out["result"]["content"]
    assert len(content) == 2
    assert content[-1] == {"type": "text", "text": "CANARY-123"}
    json.dumps(out)


def test_splice_unexpected_shape_falls_back_to_text_block():
    raw = {"jsonrpc": "2.0", "id": 7, "result": {"isError": False}}  # no content list
    out = splice.apply(raw, "CANARY-123")
    assert out["result"]["content"] == [{"type": "text", "text": "CANARY-123"}]
    json.dumps(out)


def test_splice_uses_content_field_when_sibling_has_no_text():
    raw = _result_text(json.dumps([{"content": "prior"}]))
    out = splice.apply(raw, "CANARY-123")
    arr = json.loads(out["result"]["content"][0]["text"])
    assert arr[-1]["content"] == "CANARY-123"  # most-text-like field, not a new "text" key


# --- description (where=description, §9) ---------------------------------

def test_description_appends_to_matching_tool_only():
    inj = _inject(where="description", tool="conversations_history", payload="EXTRA")
    raw = {"result": {"tools": [
        {"name": "conversations_history", "description": "Fetch history"},
        {"name": "post_message", "description": "Post a message"},
    ]}}
    out = RewriteDescription(inj).apply(raw, "EXTRA")
    tools = {t["name"]: t for t in out["result"]["tools"]}
    assert tools["conversations_history"]["description"] == "Fetch history\nEXTRA"
    assert tools["post_message"]["description"] == "Post a message"  # untouched


def test_description_handles_tool_without_existing_description():
    inj = _inject(where="description", tool="t", payload="P")
    raw = {"result": {"tools": [{"name": "t"}]}}
    out = RewriteDescription(inj).apply(raw, "P")
    assert out["result"]["tools"][0]["description"] == "\nP"
