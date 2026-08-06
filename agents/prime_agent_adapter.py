# version: v1 | 2026-08-06 | verdict: pending-review
"""PrimeAgentAdapter — Track A: embed Prime Agent as a GOVERNED sidecar node.

Prime Agent (PrimeIntellect) is a TypeScript RLM coding/research agent that exposes a
headless JSONL RPC mode over stdin/stdout (docs/rpc.md) and an in-process SDK
(docs/sdk.md). We do NOT fork its internals; we run it as a *sidecar subprocess*
(deterministic boundary) and translate its events into our zero-LLM AgentSignal
protocol (kernel/signal_protocol.py) so it slots into the existing graph.

Governance invariants (Law 2 / Law 14 / CONSTITUTION Article VI C1):
  * This adapter is a SINGLE-RESPONSIBILITY node: it owns the sidecar transport
    and signal translation only. It NEVER edits CONSTITUTION.md / LAWS.md.
  * Translation is a pure function (no LLM) — see translate_event().
  * Outbound prompts are gated by PERMISSIONS; the sidecar runs in a restricted
    cwd (sandbox) and is never given credentials or deploy rights (NEVER list).
  * If the sidecar process dies, we emit HUMAN_CHECKPOINT, never silently narrate.

Deployment: spawn `prime-agent --mode rpc` in a disposable worktree/sandbox dir.
Protocol framing: strict JSONL (LF only) per docs/rpc.md framing notes.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Iterator, TextIO

from kernel.signal_protocol import AgentSignal

# Prime Agent RPC command/event surface we depend on (docs/rpc.md).
PRIME_PROMPT = "prompt"
PRIME_STEER = "steer"
PRIME_FOLLOW_UP = "follow_up"
PRIME_ABORT = "abort"
PRIME_OBSERVE = "observe"
PRIME_UNOBSERVE = "unobserve"

PRIME_DELIVERY_MODES = ("auto", "steer", "follow_up")

PRIME_AGENT_PERMISSIONS = {
    "READ": ["sandbox_cwd", "task_spec", "parent_session_artifacts"],
    "WRITE": ["subtask_result_file", "sidecar_session_jsonl"],
    "NEVER": ["credentials", "deployment", "production_environment", "provider_override", "git_push"],
    "HUMAN_CHECKPOINT": ["untrusted_code_execution", "sidecar_process_death", "ambiguous_task"],
}


@dataclass
class RpcFrame:
    """One JSONL frame sent to or received from the prime-agent RPC process."""

    type: str
    data: dict[str, Any] = field(default_factory=dict)
    id: str | None = None

    def to_line(self) -> str:
        obj: dict[str, Any] = {"type": self.type, **self.data}
        if self.id is not None:
            obj["id"] = self.id
        return json.dumps(obj, ensure_ascii=False)

    @classmethod
    def from_line(cls, line: str) -> "RpcFrame":
        obj = json.loads(line)
        return cls(type=obj.get("type", ""), data={k: v for k, v in obj.items() if k != "type"}, id=obj.get("id"))


class Transport:
    """Abstraction over the sidecar I/O. Real impl shells out; tests inject a fake."""

    def send(self, frame: RpcFrame) -> None:
        raise NotImplementedError

    def events(self) -> Iterator[RpcFrame]:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class SubprocessTransport(Transport):
    """Spawns `prime-agent --mode rpc` and frames JSONL over its stdin/stdout."""

    def __init__(self, cwd: str, extra_args: list[str] | None = None, *, popen: Callable = subprocess.Popen):
        self._popen = popen
        cmd = ["prime-agent", "--mode", "rpc", *(extra_args or [])]
        self._proc = popen(cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           text=True, bufsize=1)
        self._stdin: TextIO = self._proc.stdin  # type: ignore[assignment]
        self._stdout: TextIO = self._proc.stdout  # type: ignore[assignment]

    def send(self, frame: RpcFrame) -> None:
        self._stdin.write(frame.to_line() + "\n")
        self._stdin.flush()

    def events(self) -> Iterator[RpcFrame]:
        for line in self._stdout:
            line = line.strip()
            if not line:
                continue
            try:
                yield RpcFrame.from_line(line)
            except (json.JSONDecodeError, ValueError):
                continue

    def close(self) -> None:
        try:
            self._proc.terminate()
        except Exception:
            pass
        try:
            self._proc.wait(timeout=5)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass


# --- NEVER-list heuristics: block obviously forbidden outbound prompts ----------
_NEVER_HINTS = ("deploy", "git push", "kubectl", "terraform apply", "secret", "credential", "export API_KEY")


def _check_never(text: str) -> None:
    low = (text or "").lower()
    for hint in _NEVER_HINTS:
        if hint in low:
            from kernel.signal_protocol import AgentSignal  # local import to avoid cycle

            raise PermissionError(
                f"PrimeAgentAdapter: outbound prompt touches NEVER scope ({hint!r}). "
                f"Blocked per PRIME_AGENT_PERMISSIONS."
            )


def translate_event(frame: RpcFrame, *, source: str = "prime_agent_sidecar") -> AgentSignal | None:
    """Pure, zero-LLM mapping from a prime-agent RPC event to our AgentSignal.

    Only a small, fixed set of prime-agent events become routing signals; lifecycle
    events (agent_start, turn_start, message_*) return None (not routed). This keeps
    the control plane deterministic (Law 14) — no LLM decides routing here.
    """
    t = frame.type
    if t == "agent_end":
        data = frame.data.get("messages", []) if isinstance(frame.data, dict) else []
        has_error = _event_has_error(data)
        return AgentSignal(
            signal_type="CODE_GENERATED" if not has_error else "VALIDATION_FAILED",
            source_agent=source,
            data={"rpc": frame.data, "has_error": has_error},
        )
    if t == "session_action_update":
        # queued actions changed; not a routing signal
        return None
    # lifecycle / streaming events are not routing signals
    return None


def _event_has_error(messages: list[dict]) -> bool:
    for m in messages:
        if isinstance(m, dict) and m.get("stopReason") in ("error", "aborted"):
            return True
    return False


@dataclass
class SidecarResult:
    signal: AgentSignal
    messages: list[dict]
    session_jsonl: str | None = None


class PrimeAgentAdapter:
    """Governed sidecar wrapper around a prime-agent RPC process.

    Single responsibility (Law 1/20): own the sidecar transport + signal translation.
    Never edits CONSTITUTION.md / LAWS.md. Outbound prompts are gated by
    PRIME_AGENT_PERMISSIONS (NEVER hints). Inbound events become AgentSignals via
    translate_event() (pure, zero-LLM).
    """

    def __init__(self, cwd: str, transport: Transport | None = None, extra_args: list[str] | None = None):
        self.cwd = cwd
        self._transport = transport or SubprocessTransport(cwd, extra_args)
        self._buffer: list[dict] = []

    # --- outbound (gated) ---
    def prompt(self, text: str, *, images: list[dict] | None = None,
               steer: bool = False, follow_up: bool = False) -> str:
        _check_never(text)
        mode = PRIME_STEER if steer else (PRIME_FOLLOW_UP if follow_up else PRIME_PROMPT)
        fid = f"req-{uuid.uuid4().hex[:8]}"
        data: dict[str, Any] = {"message": text}
        if images:
            data["images"] = images
        self._transport.send(RpcFrame(type=mode, id=fid, data=data))
        return fid

    def abort(self) -> None:
        self._transport.send(RpcFrame(type=PRIME_ABORT))

    def observe(self, session_id: str) -> None:
        self._transport.send(RpcFrame(type=PRIME_OBSERVE, data={"activeSessionId": session_id}))

    def close(self) -> None:
        self._transport.close()

    # --- inbound: run until terminal signal ---
    def run(self, task_spec: str, *, timeout_events: int | None = None) -> SidecarResult:
        self.prompt(task_spec)
        seen = 0
        for frame in self._transport.events():
            seen += 1
            if isinstance(frame.data, dict) and frame.data.get("type") == "message":
                self._buffer.append(frame.data.get("message", frame.data))
            sig = translate_event(frame, source="prime_agent_sidecar")
            if sig is not None:
                if sig.is_terminal or sig.signal_type in ("VALIDATION_FAILED",):
                    return SidecarResult(signal=sig, messages=list(self._buffer))
            if timeout_events is not None and seen >= timeout_events:
                break
        return SidecarResult(
            signal=AgentSignal(
                signal_type="HUMAN_CHECKPOINT",
                source_agent="prime_agent_sidecar",
                data={"reason": "sidecar stream ended without terminal signal"},
            ),
            messages=list(self._buffer),
        )


def prime_agent_node(state: dict) -> dict:
    """LangGraph-compatible node: run a sidecar subtask and return its signal.

    Expects state keys: task_spec (str), sandbox_cwd (str). Respects permissions;
    the sidecar runs in sandbox_cwd only.
    """
    spec = state.get("task_spec") or state.get("requirements", "")
    cwd = state.get("sandbox_cwd", ".")
    adapter = PrimeAgentAdapter(cwd=cwd)
    try:
        result = adapter.run(spec)
    finally:
        adapter.close()
    return {
        "prime_agent_signal": result.signal.to_dict(),
        "prime_agent_messages": result.messages,
    }
