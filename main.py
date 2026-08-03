"""
Graph-Based Agent System - Operational CLI Entry Point.

Runs the implemented pipeline against real requirements. LLM calls use Stepfun
only through the configured environment/.env settings. There is no production
mock fallback.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - minimal runtime fallback
    def load_dotenv(*args, **kwargs):
        return False

from agents.karpathy_pipeline import run_karpathy_pipeline

# Benchmark imports (lazy to avoid heavy deps when not needed)
def _load_benchmarks():
    try:
        from benchmarks.benchmark_suite import run_benchmarks as run_base, BENCHMARK_SCENARIOS
        return run_base, BENCHMARK_SCENARIOS
    except ImportError:
        return None, None


DEFAULT_REQUIREMENTS = """
Build a task management application with:
- User authentication
- Create, read, update, delete tasks
- Assign tasks to team members
- Set task priorities
- Add due dates
- Generate completion reports
""".strip()


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Run the Graph-Based Agent System pipeline with Stepfun-only LLM integration."
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--requirements",
        "-r",
        help="Inline natural-language requirements to process.",
    )
    input_group.add_argument(
        "--requirements-file",
        "-f",
        help="Path to a UTF-8 text file containing requirements.",
    )
    # Benchmark mode is mutually exclusive? No, allow as separate top-level flag, but add to group handling later
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run benchmark suite (4 scenarios) instead of single pipeline run.",
    )
    parser.add_argument(
        "--benchmark-extended",
        action="store_true",
        help="Run extended benchmark suite (8 scenarios).",
    )
    parser.add_argument(
        "--benchmark-reports-dir",
        default="reports",
        help="Directory to save benchmark reports (default: reports).",
    )
    parser.add_argument(
        "--project-context",
        default="",
        help="Optional project context passed to downstream agents.",
    )
    parser.add_argument(
        "--constraints",
        default="",
        help="Optional implementation/product constraints.",
    )
    parser.add_argument(
        "--history-log",
        action="append",
        default=[],
        help="Optional compact history entry in action=status format. Can be repeated.",
    )
    parser.add_argument(
        "--orchestrate-graph",
        action="store_true",
        help="Run graph execution orchestration over the assigned DAG plan.",
    )
    parser.add_argument(
        "--dispatch-domains",
        action="store_true",
        help="Dispatch domain-squad tasks during graph/pipeline execution. May call Stepfun.",
    )
    parser.add_argument(
        "--execute-code",
        action="store_true",
        help="Generate and execute code/tests for selected tasks. Use only in trusted sandbox contexts.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum surgical refinement retries.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the complete result as JSON only.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the complete JSON result.",
    )
    return parser


def parse_history_logs(entries: list[str]) -> list[dict[str, str]]:
    """Parse action=status history entries into dictionaries."""
    logs = []
    for entry in entries:
        if "=" in entry:
            action, status = entry.split("=", 1)
            logs.append({"action": action.strip(), "status": status.strip()})
        else:
            logs.append({"action": entry.strip(), "status": "unknown"})
    return logs


def load_requirements(args: argparse.Namespace) -> str:
    """Load requirements from CLI args or return a safe example."""
    if args.requirements_file:
        return Path(args.requirements_file).read_text(encoding="utf-8").strip()
    if args.requirements:
        return args.requirements.strip()
    return DEFAULT_REQUIREMENTS


def compact_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Build a concise human-readable summary payload."""
    return {
        "success": result.get("success"),
        "stage": result.get("stage"),
        "tasks": len(result.get("tasks", [])),
        "quality_score": result.get("quality_score"),
        "final_quality_score": result.get("final_quality_score"),
        "assignment_success": result.get("assignment_success"),
        "execution_plan_items": len(result.get("execution_plan", [])),
        "graph_execution_success": result.get("graph_execution", {}).get("success"),
        "domain_dispatch_success": result.get("domain_dispatch", {}).get("success"),
        "violations": result.get("violations", []),
    }


def run_from_args(args: argparse.Namespace) -> dict[str, Any]:
    """Run pipeline from parsed CLI arguments."""
    requirements = load_requirements(args)
    history_logs = parse_history_logs(args.history_log)
    return run_karpathy_pipeline(
        requirements=requirements,
        project_context=args.project_context,
        constraints=args.constraints,
        history_logs=history_logs,
        execute_code=args.execute_code,
        dispatch_domains=args.dispatch_domains,
        orchestrate_graph=args.orchestrate_graph,
        max_retries=args.max_retries,
    )


def run_benchmark_mode(args: argparse.Namespace) -> int:
    """Run benchmark suite mode"""
    try:
        from benchmarks.benchmark_suite import run_benchmarks as run_base
        from benchmarks.report_generator import save_benchmark_report
        from benchmarks.metrics import compute_full_metrics
        from pathlib import Path
    except ImportError as e:
        print(f"❌ Failed to import benchmark modules: {e}", file=sys.stderr)
        return 1

    # Decide extended or base
    if args.benchmark_extended:
        try:
            from benchmarks.extended_scenarios import get_full_scenarios
            from scripts.run_benchmarks import run_extended_benchmarks
            scenarios = get_full_scenarios()
            print(f"🚀 Running EXTENDED benchmark suite ({len(scenarios)} scenarios)")
            result = run_extended_benchmarks(scenarios)
        except ImportError as e:
            print(f"❌ Extended suite import failed: {e}, falling back to base", file=sys.stderr)
            result = run_base()
    else:
        print("🚀 Running BASE benchmark suite (4 scenarios)")
        result = run_base()

    # Advanced metrics
    try:
        advanced = compute_full_metrics(result)
        print()
        print("=" * 80)
        print(f"  Advanced Metrics - Health Score: {advanced.get('overall_health_score',0)}/100")
        print("=" * 80)
        print(json.dumps(advanced, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"⚠️ Metrics calc failed: {e}")
        advanced = {}

    # Save reports
    try:
        reports_dir = args.benchmark_reports_dir
        Path(reports_dir).mkdir(parents=True, exist_ok=True)
        paths = save_benchmark_report(result, reports_dir)
        print()
        print(f"📄 JSON report saved: {paths['json']}")
        print(f"📝 Markdown report saved: {paths['markdown']}")
        if args.output:
            Path(args.output).write_text(json.dumps({"benchmark": result, "advanced": advanced}, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"📦 Full output also written to: {args.output}")
    except Exception as e:
        print(f"⚠️ Failed to save reports: {e}")

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    # Success if >=50% success rate
    success_rate = result.get("summary", {}).get("success_rate_percent", 0)
    return 0 if success_rate >= 50 else 1


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)

    # Benchmark mode
    if args.benchmark or args.benchmark_extended:
        return run_benchmark_mode(args)

    result = run_from_args(args)

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("=" * 80)
        print("Graph-Based Agent System - Run Summary")
        print("=" * 80)
        print(json.dumps(compact_summary(result), indent=2, ensure_ascii=False))
        print("=" * 80)
        if args.output:
            print(f"Full result written to: {args.output}")

    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
