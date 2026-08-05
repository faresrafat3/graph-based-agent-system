# version: v1 | 2026-08-05 | verdict: pending-review
"""T1-fix#3 — disk-backed checkpoint saver for the systems_layer meta-loop.

The strong-model review (#3) measured that the live meta-loop used `MemorySaver`, which is
VOLATILE: all graph state (incl. the `cycle_log` = the system's persisted "life", P5) is lost
on every process restart. This module provides a dependency-free, JSONL-backed checkpoint
saver that conforms to langgraph's BaseCheckpointSaver interface, so the meta-loop's state
survives restarts. No new dependency is introduced (langgraph-checkpoint-sqlite is not installed).

The bounded cycle_log (see agents/context_system_view.py MAX_CYCLE_LOG) plus this durable
saver together close the context-scaling break: the view is bounded AND its history is on disk.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Iterator

from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple


class JsonlCheckpointSaver(BaseCheckpointSaver):
    """Minimal disk-backed checkpoint saver (JSONL, one row per write).

    Conforms to the langgraph checkpointer contract (put / get_tuple / put_writes / list)
    with a permissive JSON serde. Checkpoints are appended to ``path`` and read back by
    thread_id, so the systems_layer meta-loop state is durable across restarts.
    """

    def __init__(self, path: str | Path = "system/measurements/systems_layer_checkpoints.jsonl") -> None:
        super().__init__()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        # in-memory index: thread_id -> list of (checkpoint_tuple dict) newest last
        self._index: dict[str, list[dict]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self._lock:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self._index.setdefault(row["thread_id"], []).append(row)

    @staticmethod
    def _ser(obj: Any) -> Any:
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            # fall back to a lossy-but-safe representation for non-JSON-native objects
            return {"__repr__": repr(obj)}

    def _dump(self, row: dict) -> None:
        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            self._index.setdefault(row["thread_id"], []).append(row)

    def put(self, config: dict, checkpoint: Any, metadata: Any, new_versions: Any) -> dict:
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        row = {
            "thread_id": thread_id,
            "checkpoint": self._ser(checkpoint),
            "metadata": self._ser(metadata),
            "parent": (config.get("configurable", {}).get("checkpoint_id")),
        }
        self._dump(row)
        return {"configurable": {"thread_id": thread_id, "checkpoint_id": _ckpt_id(checkpoint)}}

    def get_tuple(self, config: dict) -> CheckpointTuple | None:
        thread_id = config.get("configurable", {}).get("thread_id")
        if thread_id is None:
            return None
        rows = self._index.get(thread_id, [])
        if not rows:
            return None
        row = rows[-1]
        return CheckpointTuple(
            config=config,
            checkpoint=row["checkpoint"],
            metadata=row.get("metadata", {}),
            parent_config={"configurable": {"thread_id": thread_id, "checkpoint_id": row.get("parent")}}
            if row.get("parent") else None,
        )

    def put_writes(self, config: dict, writes: Any, task_id: str, task_path: str = "") -> None:
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        row = {
            "thread_id": thread_id,
            "writes": self._ser(list(writes)),
            "task_id": task_id,
            "task_path": task_path,
            "parent": config.get("configurable", {}).get("checkpoint_id"),
        }
        self._dump(row)

    def list(self, config: dict | None, *, filter: dict | None = None,
             before: dict | None = None, limit: int | None = None) -> Iterator[CheckpointTuple]:
        thread_id = config.get("configurable", {}).get("thread_id") if config else None
        rows = self._index.get(thread_id, []) if thread_id else []
        for row in rows:
            yield CheckpointTuple(
                config={"configurable": {"thread_id": row["thread_id"]}},
                checkpoint=row["checkpoint"],
                metadata=row.get("metadata", {}),
            )


def _ckpt_id(checkpoint: Any) -> str:
    import uuid
    cid = getattr(checkpoint, "id", None)
    return cid or uuid.uuid4().hex
