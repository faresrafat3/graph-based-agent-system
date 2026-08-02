import sys, os, json, tempfile
from pathlib import Path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from benchmarks.report_generator import save_benchmark_report

def fake_result():
    return {
        "summary": {
            "total_scenarios": 4,
            "success_rate_percent": 75.0,
            "effective_success_rate_percent": 100.0,
            "average_quality_score": 0.85,
            "average_signal_to_noise": 0.9,
            "total_tasks_generated": 10,
            "total_duration_seconds": 10.5,
            "average_latency_seconds": 2.6,
            "p95_latency_seconds": 3.0,
        },
        "details": [
            {"scenario_id": "s1", "name": "Test1", "category": "Standard", "success": True, "quality_score": 0.9, "signal_to_noise": 1.0, "tasks_generated": 3, "violations_count": 0, "duration_seconds": 2.0, "error": None},
            {"scenario_id": "s2", "name": "Test2", "category": "Security", "success": True, "quality_score": 0.8, "signal_to_noise": 0.9, "tasks_generated": 4, "violations_count": 0, "duration_seconds": 3.0, "error": None},
        ]
    }

def test_report_generator_creates_files():
    with tempfile.TemporaryDirectory() as tmp:
        res = fake_result()
        paths = save_benchmark_report(res, reports_dir=tmp)
        assert Path(paths["json"]).exists()
        assert Path(paths["markdown"]).exists()
        # Check latest files exist
        assert Path(tmp, "latest_benchmark.json").exists()
        assert Path(tmp, "latest_benchmark.md").exists()
        # Validate JSON content
        data = json.loads(Path(paths["json"]).read_text())
        assert "benchmark_result" in data
        assert "advanced_metrics" in data
        assert "generated_at" in data

def test_report_markdown_content():
    with tempfile.TemporaryDirectory() as tmp:
        res = fake_result()
        paths = save_benchmark_report(res, reports_dir=tmp)
        md = Path(paths["markdown"]).read_text()
        assert "Benchmark Report" in md
        assert "Summary" in md
        assert "Scenario Details" in md
