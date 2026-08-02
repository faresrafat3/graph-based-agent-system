"""
Professional Benchmark Runner - Wraps benchmark_suite with report generation
Supports both base (4) and extended (8) scenarios, live LLM or mocked.
Usage:
  python scripts/run_benchmarks.py                      # base 4, mocked if no key, live if key
  python scripts/run_benchmarks.py --extended           # 8 scenarios
  python scripts/run_benchmarks.py --output reports/my_report.json  # custom path
  python scripts/run_benchmarks.py --live-only          # require STEPFUN_API_KEY
"""

import sys
import os
import argparse
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.benchmark_suite import run_benchmarks as run_base_benchmarks, BENCHMARK_SCENARIOS
from benchmarks.report_generator import save_benchmark_report, ensure_reports_dir
from benchmarks.metrics import compute_full_metrics

# Optional extended
try:
    from benchmarks.extended_scenarios import EXTENDED_BENCHMARKS, get_full_scenarios
    HAS_EXTENDED = True
except ImportError:
    HAS_EXTENDED = False
    EXTENDED_BENCHMARKS = []
    def get_full_scenarios():
        return BENCHMARK_SCENARIOS


def run_extended_benchmarks(scenarios):
    """Run custom scenario list (used for extended suite)"""
    from agents.karpathy_pipeline import run_karpathy_pipeline
    
    print("=" * 80)
    print("  Karpathy Agentic System - Extended Benchmark Suite")
    print("=" * 80)
    print()
    
    results = []
    total_start = time.time()
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"[{i}/{len(scenarios)}] Running: {scenario['name']} ({scenario['category']})...")
        start_t = time.time()
        try:
            res = run_karpathy_pipeline(
                requirements=scenario["requirements"],
                project_context=scenario.get("project_context", ""),
                constraints=scenario.get("constraints", "")
            )
            duration = round(time.time() - start_t, 3)
            entry = {
                "scenario_id": scenario["id"],
                "name": scenario["name"],
                "category": scenario["category"],
                "success": res.get("success", False),
                "quality_score": res.get("quality_score", 0.0),
                "signal_to_noise": res.get("context_signal_to_noise", 1.0),
                "refinement_attempts": res.get("refinement_attempts", 0),
                "tasks_generated": len(res.get("tasks", [])),
                "violations_count": len(res.get("violations", [])),
                "duration_seconds": duration,
                "error": None
            }
        except Exception as e:
            duration = round(time.time() - start_t, 3)
            entry = {
                "scenario_id": scenario["id"],
                "name": scenario["name"],
                "category": scenario["category"],
                "success": False,
                "quality_score": 0.0,
                "signal_to_noise": 0.0,
                "refinement_attempts": 0,
                "tasks_generated": 0,
                "violations_count": 1,
                "duration_seconds": duration,
                "error": str(e)
            }
        results.append(entry)
        status_icon = "✅ PASS" if entry["success"] else "❌ FAIL/BLOCKED"
        print(f"    Status: {status_icon} | Quality: {entry['quality_score']} | Time: {duration}s")
        print()
    
    total_duration = round(time.time() - total_start, 3)
    total_runs = len(results)
    passed_runs = sum(1 for r in results if r["success"])
    success_rate = round((passed_runs / total_runs) * 100, 2) if total_runs else 0
    avg_quality = round(sum(r["quality_score"] for r in results) / total_runs, 2) if total_runs else 0
    avg_signal = round(sum(r["signal_to_noise"] for r in results) / total_runs, 4) if total_runs else 0
    total_tasks = sum(r["tasks_generated"] for r in results)
    
    print("=" * 80)
    print("  Extended Benchmark Summary")
    print("=" * 80)
    print(f"  Total Scenarios: {total_runs}")
    print(f"  Success Rate: {success_rate}% ({passed_runs}/{total_runs})")
    print(f"  Avg Quality: {avg_quality} / 1.0")
    print(f"  Avg Signal-to-Noise: {avg_signal}")
    print(f"  Total Tasks: {total_tasks}")
    print(f"  Total Time: {total_duration}s")
    print("=" * 80)
    
    return {
        "summary": {
            "total_scenarios": total_runs,
            "success_rate_percent": success_rate,
            "average_quality_score": avg_quality,
            "average_signal_to_noise": avg_signal,
            "total_tasks_generated": total_tasks,
            "total_duration_seconds": total_duration
        },
        "details": results
    }


def main():
    parser = argparse.ArgumentParser(description="Run Karpathy benchmarks with report generation")
    parser.add_argument("--extended", action="store_true", help="Run extended 8-scenario suite")
    parser.add_argument("--reports-dir", default="reports", help="Directory to save reports")
    parser.add_argument("--live-only", action="store_true", help="Require STEPFUN_API_KEY, fail if not present")
    parser.add_argument("--json-only", action="store_true", help="Print JSON result only")
    args = parser.parse_args()
    
    # Check API key
    api_key = os.getenv("STEPFUN_API_KEY")
    if args.live_only and not api_key:
        print("❌ --live-only requires STEPFUN_API_KEY env var")
        return 1
    if api_key:
        print(f"🔑 STEPFUN_API_KEY detected, will run live LLM calls")
    else:
        print(f"⚠️  No STEPFUN_API_KEY, running with whatever pipeline provides (may use fallback in tests)")
    
    # Run
    if args.extended:
        if not HAS_EXTENDED:
            print("❌ Extended scenarios not available")
            return 1
        scenarios = get_full_scenarios()
        result = run_extended_benchmarks(scenarios)
    else:
        result = run_base_benchmarks()
    
    # Metrics
    advanced = compute_full_metrics(result)
    
    # Save reports
    reports_dir = args.reports_dir
    ensure_reports_dir(reports_dir)
    artifact_paths = save_benchmark_report(result, reports_dir)
    
    print()
    print(f"📄 JSON report: {artifact_paths['json']}")
    print(f"📝 Markdown report: {artifact_paths['markdown']}")
    print(f"🏥 Health Score: {advanced.get('overall_health_score',0)}/100")
    
    if args.json_only:
        print(json.dumps(result, indent=2))
    
    return 0 if result["summary"]["success_rate_percent"] >= 50 else 1


if __name__ == "__main__":
    sys.exit(main())
