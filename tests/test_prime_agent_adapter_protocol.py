# version: v1 | 2026-08-08 | verdict: pending-review
"""Protocol-conformance tests for agents/prime_agent_adapter.py.

Asserted against the ACTUAL published RPC specification
(prime-agent packages/coding-agent/docs/rpc.md, v0.7.x, MIT), not against our
assumptions. Each test names the spec section it protects.

The sidecar is an untrusted, out-of-process collaborator. Every one of these
tests exists because the failure it prevents is SILENT: the adapter hangs, or
reports success, while the real run failed.

PORTED-FROM: packages/coding-agent/docs/rpc.md @ prime-agent v0.7.x
"""

from __future__ import annotations

from agents.prime_agent_adapter import (
    PrimeAgentAdapter,
    RpcFrame,
    Transport,
    translate_event,
)


class FakeTransport(Transport):
    """Replays a scripted list of frames; records what was sent."""

    def __init__(self, frames: list[RpcFrame]):
        self._frames = frames
        self.sent: list[RpcFrame] = []
        self.closed = False

    def send(self, frame: RpcFrame) -> None:
        self.sent.append(frame)

    def events(self):
        yield from self._frames

    def close(self) -> None:
        self.closed = True


def _run(frames: list[RpcFrame]):
    adapter = PrimeAgentAdapter(cwd="/tmp", transport=FakeTransport(frames))
    return adapter.run("do the thing")


# --- rpc.md:1225-1240 "Error Handling": a failed command returns success:false ---


def test_failed_command_response_does_not_hang():
    """A command rejected by the sidecar must terminate the run, not wait forever.

    Spec: `{"type":"response","command":...,"success":false,"error":...}`.
    Before this test the adapter ignored `response` frames entirely, so a rejected
    prompt left run() blocked on a stream that would never produce agent_end.
    """
    result = _run([
        RpcFrame(type="response", data={"command": "prompt", "success": False,
                                        "error": "Model not found: invalid/model"}),
    ])
    assert result.signal.signal_type == "HUMAN_CHECKPOINT"
    assert "Model not found" in str(result.signal.data)


def test_successful_command_response_is_not_terminal():
    """`success: true` is an acknowledgement, not a result; the run continues."""
    result = _run([
        RpcFrame(type="response", data={"command": "prompt", "success": True}),
        RpcFrame(type="agent_end", data={"messages": [{"stopReason": "stop"}]}),
    ])
    assert result.signal.signal_type == "CODE_GENERATED"


# --- rpc.md:1020-1031 extension_error ---


def test_extension_error_is_surfaced_not_swallowed():
    """An extension throwing must not be silently dropped (fail-loud, Law 3)."""
    result = _run([
        RpcFrame(type="extension_error", data={"extensionPath": "/x.ts",
                                               "event": "tool_call",
                                               "error": "boom"}),
        RpcFrame(type="agent_end", data={"messages": [{"stopReason": "stop"}]}),
    ])
    assert result.errors, "extension_error must be recorded on the result"
    assert "boom" in result.errors[0]


# --- rpc.md:988-1018 auto_retry_start / auto_retry_end ---


def test_auto_retry_is_observable():
    """A transient-failure retry is an INFRA event; conflating it with clean work
    corrupts any capability measurement built on these runs."""
    result = _run([
        RpcFrame(type="auto_retry_start", data={"attempt": 1}),
        RpcFrame(type="auto_retry_end", data={"attempt": 1, "success": True}),
        RpcFrame(type="agent_end", data={"messages": [{"stopReason": "stop"}]}),
    ])
    assert result.retries == 1, "retries must be counted, not invisible"


# --- rpc.md:957-986 compaction_start / compaction_end ---


def test_compaction_is_observable():
    """Compaction changes what the agent can remember; it must be recorded."""
    result = _run([
        RpcFrame(type="compaction_start", data={}),
        RpcFrame(type="compaction_end", data={}),
        RpcFrame(type="agent_end", data={"messages": [{"stopReason": "stop"}]}),
    ])
    assert result.compactions == 1


# --- rpc.md:789-808 the message lifecycle is *_start/_update/_end ---


def test_message_end_is_buffered_once():
    """Spec emits message_start/message_update/message_end. Deltas must not be
    buffered as if they were complete messages."""
    result = _run([
        RpcFrame(type="message_start", data={}),
        RpcFrame(type="message_update", data={"delta": "par"}),
        RpcFrame(type="message_update", data={"delta": "tial"}),
        RpcFrame(type="message_end", data={"message": {"role": "assistant", "content": "partial"}}),
        RpcFrame(type="agent_end", data={"messages": [{"stopReason": "stop"}]}),
    ])
    assert len(result.messages) == 1, "streaming deltas must not each become a message"
    assert result.messages[0]["content"] == "partial"


# --- rpc.md:818-827 agent_end carries stopReason ---


def test_agent_end_error_stop_reason_is_a_failure():
    result = _run([
        RpcFrame(type="agent_end", data={"messages": [{"stopReason": "error"}]}),
    ])
    assert result.signal.signal_type == "VALIDATION_FAILED"


def test_stream_ending_without_terminal_frame_escalates():
    """A sidecar that dies mid-run must escalate, never look like success."""
    result = _run([RpcFrame(type="turn_start", data={})])
    assert result.signal.signal_type == "HUMAN_CHECKPOINT"


# --- rpc.md:27-37 framing: LF only, tolerate a trailing CR ---


def test_frame_parsing_tolerates_trailing_cr():
    """Spec: accept optional \\r\\n input by stripping a trailing \\r."""
    frame = RpcFrame.from_line('{"type":"agent_end","messages":[]}\r')
    assert frame.type == "agent_end"


def test_unicode_separators_are_not_record_delimiters():
    """Spec:27-37 — U+2028/U+2029 are valid INSIDE a JSON string and must not
    split records. Python file iteration already splits on \\n only; this test
    pins that a payload containing them survives a round-trip intact."""
    payload = '{"type":"agent_end","messages":[{"text":"a\u2028b\u2029c"}]}'
    frame = RpcFrame.from_line(payload)
    assert frame.type == "agent_end"
    assert frame.data["messages"][0]["text"] == "a\u2028b\u2029c"


# --- governance: the NEVER list is enforced before anything leaves the process ---


def test_never_list_blocks_before_send():
    import pytest

    transport = FakeTransport([])
    adapter = PrimeAgentAdapter(cwd="/tmp", transport=transport)
    with pytest.raises(PermissionError):
        adapter.prompt("please git push to production")
    assert transport.sent == [], "a blocked prompt must never reach the sidecar"


def test_translate_event_is_pure_and_zero_llm():
    """Routing stays deterministic (Law 14): same frame in, same signal out."""
    frame = RpcFrame(type="agent_end", data={"messages": [{"stopReason": "stop"}]})
    a = translate_event(frame)
    b = translate_event(frame)
    assert a is not None and b is not None
    assert a.signal_type == b.signal_type == "CODE_GENERATED"
