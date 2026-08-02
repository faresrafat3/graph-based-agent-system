"""
Benchmark Comparator - Compare two benchmark runs and show delta
"""

import json
from pathlib import Path
from typing import Dict, Any


def load_report(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    # Support both wrapped and raw formats
    if "benchmark_result" in data:
        return data
    return {"benchmark_result": data, "advanced_metrics": {}}


def compare_reports(old_path: str | Path, new_path: str | Path) -> Dict[str, Any]:
    old = load_report(old_path)
    new = load_report(new_path)
    
    old_summary = old.get("benchmark_result", {}).get("summary", {})
    new_summary = new.get("benchmark_result", {}).get("summary", {})
    
    old_details = {d["scenario_id"]: d for d in old.get("benchmark_result", {}).get("details", [])}
    new_details = {d["scenario_id"]: d for d in new.get("benchmark_result", {}).get("details", [])}
    
    def delta(a, b):
        return round(b - a, 3) if isinstance(a, (int,float)) and isinstance(b, (int,float)) else None
    
    summary_delta = {}
    for key in set(old_summary.keys()) | set(new_summary.keys()):
        ov = old_summary.get(key)
        nv = new_summary.get(key)
        if isinstance(ov, (int,float)) and isinstance(nv, (int,float)):
            summary_delta[key] = {"old": ov, "new": nv, "delta": delta(ov, nv), "improved": nv >= ov if "rate" in key or "score" in key or "signal" in key else nv <= ov}
    
    scenario_deltas = []
    all_ids = set(old_details.keys()) | set(new_details.keys())
    for sid in all_ids:
        od = old_details.get(sid, {})
        nd = new_details.get(sid, {})
        scenario_deltas.append({
            "scenario_id": sid,
            "old_success": od.get("success"),
            "new_success": nd.get("success"),
            "old_quality": od.get("quality_score"),
            "new_quality": nd.get("quality_score"),
            "quality_delta": delta(od.get("quality_score",0), nd.get("quality_score",0)),
            "old_duration": od.get("duration_seconds"),
            "new_duration": nd.get("duration_seconds"),
            "duration_delta": delta(od.get("duration_seconds",0), nd.get("duration_seconds",0)),
            "status_changed": od.get("success") != nd.get("success"),
        })
    
    old_health = old.get("advanced_metrics", {}).get("overall_health_score", 0)
    new_health = new.get("advanced_metrics", {}).get("overall_health_score", 0)
    
    return {
        "old_file": str(old_path),
        "new_file": str(new_path),
        "summary_delta": summary_delta,
        "scenario_deltas": scenario_deltas,
        "old_health": old_health,
        "new_health": new_health,
        "health_delta": round(new_health - old_health,2),
        "overall_improved": new_health >= old_health
    }


def format_comparison_markdown(comp: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"# 📊 Benchmark Comparison")
    lines.append("")
    lines.append(f"- **Old:** {comp['old_file']}")
    lines.append(f"- **New:** {comp['new_file']}")
    lines.append(f"- **Health:** {comp['old_health']} → {comp['new_health']} (Δ {comp['health_delta']:+})")
    lines.append(f"- **Overall:** {'✅ Improved' if comp['overall_improved'] else '❌ Regressed'}")
    lines.append("")
    lines.append("## Summary Deltas")
    lines.append("")
    lines.append("| Metric | Old | New | Δ | Trend |")
    lines.append("|--------|-----|-----|---|-------|")
    for k, v in comp["summary_delta"].items():
        trend = "📈" if v["improved"] else "📉"
        lines.append(f"| {k} | {v['old']} | {v['new']} | {v['delta']:+} | {trend} |")
    lines.append("")
    lines.append("## Scenario Deltas")
    lines.append("")
    lines.append("| Scenario | Old Success | New Success | Quality Δ | Duration Δ | Changed |")
    lines.append("|----------|-------------|-------------|-----------|------------|---------|")
    for s in comp["scenario_deltas"]:
        changed_icon = "⚠️" if s["status_changed"] else ""
        lines.append(f"| {s['scenario_id']} | {s['old_success']} | {s['new_success']} | {s['quality_delta']} | {s['duration_delta']} | {changed_icon} |")
    lines.append("")
    return "\n".join(lines)
