"""
Benchmark Report Generator - Produces JSON + Markdown reports with advanced metrics
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

try:
    from benchmarks.metrics import compute_full_metrics
except ImportError:
    from metrics import compute_full_metrics


def ensure_reports_dir(reports_dir: str = "reports") -> Path:
    p = Path(reports_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def generate_json_report(benchmark_result: Dict[str, Any], reports_dir: str = "reports") -> Path:
    """Save full benchmark result as timestamped JSON"""
    reports_path = ensure_reports_dir(reports_dir)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    full_metrics = compute_full_metrics(benchmark_result)
    
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_result": benchmark_result,
        "advanced_metrics": full_metrics,
        "environment": {
            "python": os.sys.version,
        }
    }
    
    json_path = reports_path / f"benchmark_report_{timestamp}.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # Also write latest.json
    latest_path = reports_path / "latest_benchmark.json"
    latest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    
    return json_path


def generate_markdown_report(benchmark_result: Dict[str, Any], reports_dir: str = "reports") -> Path:
    """Generate a human-readable Markdown benchmark report"""
    reports_path = ensure_reports_dir(reports_dir)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    pretty_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    full_metrics = compute_full_metrics(benchmark_result)
    summary = benchmark_result.get("summary", {})
    details = benchmark_result.get("details", [])
    latency = full_metrics.get("latency", {})
    by_category = full_metrics.get("by_category", {})
    security = full_metrics.get("security", {})
    hygiene = full_metrics.get("context_hygiene", {})
    quality_dist = full_metrics.get("quality_distribution", {})
    
    md_lines = []
    md_lines.append(f"# 📊 Benchmark Report - {pretty_time}")
    md_lines.append("")
    md_lines.append(f"**Generated:** {pretty_time}")
    md_lines.append(f"**Total Scenarios:** {summary.get('total_scenarios', len(details))}")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    md_lines.append("## 🏆 Summary")
    md_lines.append("")
    md_lines.append("| Metric | Value |")
    md_lines.append("|--------|-------|")
    md_lines.append(f"| Success Rate | {summary.get('success_rate_percent', 0)}% ({sum(1 for d in details if d.get('success'))}/{len(details)}) |")
    md_lines.append(f"| Avg Quality Score | {summary.get('average_quality_score', 0)} / 1.0 |")
    md_lines.append(f"| Avg Signal-to-Noise | {summary.get('average_signal_to_noise', 0)} |")
    md_lines.append(f"| Total Tasks Generated | {summary.get('total_tasks_generated', 0)} |")
    md_lines.append(f"| Total Duration | {summary.get('total_duration_seconds', latency.get('total',0))}s |")
    md_lines.append(f"| Overall Health Score | {full_metrics.get('overall_health_score',0)} / 100 |")
    md_lines.append("")
    
    md_lines.append("## ⚡ Latency Metrics")
    md_lines.append("")
    md_lines.append("| Metric | Value |")
    md_lines.append("|--------|-------|")
    md_lines.append(f"| Mean | {latency.get('mean',0)}s |")
    md_lines.append(f"| P50 (Median) | {latency.get('p50',0)}s |")
    md_lines.append(f"| P95 | {latency.get('p95',0)}s |")
    md_lines.append(f"| Min | {latency.get('min',0)}s |")
    md_lines.append(f"| Max | {latency.get('max',0)}s |")
    md_lines.append("")
    
    md_lines.append("## 🛡️ Security / Defense Metrics")
    md_lines.append("")
    md_lines.append("| Metric | Value |")
    md_lines.append("|--------|-------|")
    md_lines.append(f"| Evaluated | {security.get('evaluated',0)} |")
    md_lines.append(f"| Blocked | {security.get('blocked',0)} |")
    md_lines.append(f"| Defense Rate | {security.get('defense_rate',0)}% |")
    if security.get("details"):
        md_lines.append(f"| Details | {security.get('details')} |")
    md_lines.append("")
    
    md_lines.append("## 🧹 Context Hygiene")
    md_lines.append("")
    md_lines.append("| Metric | Value |")
    md_lines.append("|--------|-------|")
    md_lines.append(f"| Avg Signal/Noise | {hygiene.get('average_signal_to_noise',0)} |")
    if hygiene.get("noisy_scenarios_avg_signal") is not None:
        md_lines.append(f"| Noisy Scenarios Avg | {hygiene.get('noisy_scenarios_avg_signal')} |")
    md_lines.append(f"| Filter Effective | {hygiene.get('noise_filter_effective', False)} |")
    md_lines.append("")
    
    md_lines.append("## 🎯 Quality Distribution")
    md_lines.append("")
    md_lines.append("| Metric | Value |")
    md_lines.append("|--------|-------|")
    md_lines.append(f"| Mean Quality | {quality_dist.get('mean',0)} |")
    md_lines.append(f"| Median Quality | {quality_dist.get('median',0)} |")
    md_lines.append(f"| Min | {quality_dist.get('min',0)} |")
    md_lines.append(f"| Max | {quality_dist.get('max',0)} |")
    md_lines.append("")
    
    md_lines.append("## 📂 By Category")
    md_lines.append("")
    md_lines.append("| Category | Total | Passed | Success Rate | Avg Quality |")
    md_lines.append("|----------|-------|--------|--------------|-------------|")
    for cat, data in by_category.items():
        md_lines.append(f"| {cat} | {data.get('total',0)} | {data.get('passed',0)} | {data.get('success_rate',0)}% | {data.get('avg_quality',0)} |")
    md_lines.append("")
    
    md_lines.append("## 📋 Scenario Details")
    md_lines.append("")
    md_lines.append("| # | Scenario | Category | Success | Quality | Signal/Noise | Tasks | Duration |")
    md_lines.append("|---|----------|----------|---------|---------|--------------|-------|----------|")
    for i, d in enumerate(details, 1):
        status = "✅" if d.get("success") else "❌"
        md_lines.append(
            f"| {i} | {d.get('name','')} ({d.get('scenario_id','')}) | {d.get('category','')} | {status} | {d.get('quality_score',0)} | {d.get('signal_to_noise',0)} | {d.get('tasks_generated',0)} | {d.get('duration_seconds',0)}s |"
        )
    md_lines.append("")
    
    md_lines.append("### Failures / Errors")
    md_lines.append("")
    has_failures = False
    for d in details:
        if not d.get("success") or d.get("error"):
            has_failures = True
            md_lines.append(f"- **{d.get('scenario_id')} - {d.get('name')}**: Success={d.get('success')}, Error={d.get('error')}, Violations={d.get('violations_count')}")
    if not has_failures:
        md_lines.append("- No failures - all scenarios passed or correctly blocked.")
    md_lines.append("")
    
    md_lines.append("---")
    md_lines.append("")
    md_lines.append("## 🔍 Interpretation")
    md_lines.append("")
    md_lines.append(f"- **Health Score {full_metrics.get('overall_health_score',0)}/100**: Composite of success rate, quality, defense, hygiene")
    md_lines.append("- **Expected Success Rate**: 75%+ for 4-scenario suite (3 pass + 1 adversarial blocked)")
    md_lines.append("- **For 8-scenario suite**: 75%+ still healthy (6/8 + 1 vague correctly handled)")
    md_lines.append("")
    md_lines.append("## 📎 Artifacts")
    md_lines.append("")
    md_lines.append("- JSON report: `reports/benchmark_report_{timestamp}.json`")
    md_lines.append("- Latest JSON: `reports/latest_benchmark.json`")
    md_lines.append("")
    
    content = "\n".join(md_lines)
    
    md_path = reports_path / f"benchmark_report_{timestamp}.md"
    md_path.write_text(content, encoding="utf-8")
    
    latest_md = reports_path / "latest_benchmark.md"
    latest_md.write_text(content, encoding="utf-8")
    
    # Also update README style benchmark summary at root?
    # Keep it in reports only
    
    return md_path


def save_benchmark_report(benchmark_result: Dict[str, Any], reports_dir: str = "reports") -> Dict[str, Path]:
    """Generate both JSON and Markdown reports"""
    json_path = generate_json_report(benchmark_result, reports_dir)
    md_path = generate_markdown_report(benchmark_result, reports_dir)
    return {"json": json_path, "markdown": md_path}
