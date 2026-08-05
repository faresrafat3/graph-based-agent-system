"""TDD test for T3 — forge scale demo script runs and proves no clone/fork at scale."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_forge_scale_demo_produces_clone_free_batch():
    out = ROOT / "benchmarks" / "results" / "forge_scale_test.jsonl"
    if out.exists():
        out.unlink()
    r = subprocess.run(
        [sys.executable, "scripts/forge_scale_demo.py", "--count", "210",
         "--out", str(out)],
        cwd=str(ROOT), capture_output=True, text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT)},
    )
    assert r.returncode == 0, r.stderr
    row = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert row["batch_size"] == 210
    assert row["distinct_behavior_hashes"] == 210
    assert row["clone_free"] is True
    assert row["topology_extends"] == "systems_layer"
