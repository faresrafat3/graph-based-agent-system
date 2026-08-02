import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from benchmarks.metrics import compute_full_metrics, calculate_latency_metrics

def fake_result():
    return {
        "summary": {
            "total_scenarios": 4,
            "success_rate_percent": 75.0,
            "average_quality_score": 0.85,
            "average_signal_to_noise": 0.9,
            "total_tasks_generated": 10,
            "total_duration_seconds": 10.5
        },
        "details": [
            {"scenario_id": "scenario_1", "category": "Standard", "success": True, "quality_score": 0.9, "signal_to_noise": 1.0, "tasks_generated": 3, "violations_count": 0, "duration_seconds": 2.0},
            {"scenario_id": "scenario_2", "category": "Security", "success": True, "quality_score": 0.8, "signal_to_noise": 0.9, "tasks_generated": 4, "violations_count": 0, "duration_seconds": 3.0},
            {"scenario_id": "scenario_3", "category": "Context Hygiene", "success": True, "quality_score": 0.85, "signal_to_noise": 0.7, "tasks_generated": 3, "violations_count": 0, "duration_seconds": 2.5},
            {"scenario_id": "scenario_4_security_adversarial", "category": "Permission Invariants", "success": False, "quality_score": 0.0, "signal_to_noise": 0.9, "tasks_generated": 0, "violations_count": 1, "duration_seconds": 1.0},
        ]
    }

def test_latency_metrics():
    details = fake_result()["details"]
    m = calculate_latency_metrics(details)
    assert m["total"] == 8.5
    assert m["mean"] > 0
    assert "p95" in m

def test_full_metrics():
    res = fake_result()
    metrics = compute_full_metrics(res)
    assert "latency" in metrics
    assert "by_category" in metrics
    assert "security" in metrics
    assert "context_hygiene" in metrics
    assert "overall_health_score" in metrics
    assert metrics["overall_health_score"] > 0
    assert metrics["security"]["evaluated"] >= 1
