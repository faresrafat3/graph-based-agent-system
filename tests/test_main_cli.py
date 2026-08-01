import argparse
import json

import main as main_module


def test_parse_history_logs():
    logs = main_module.parse_history_logs(["curate=ok", "execute"])
    assert logs == [
        {"action": "curate", "status": "ok"},
        {"action": "execute", "status": "unknown"},
    ]


def test_load_requirements_inline():
    args = argparse.Namespace(requirements="Build API", requirements_file=None)
    assert main_module.load_requirements(args) == "Build API"


def test_compact_summary():
    result = {
        "success": True,
        "stage": "complete",
        "tasks": [{"id": "task_1"}],
        "execution_plan": [{"task_id": "task_1"}],
        "domain_dispatch": {"success": True},
        "graph_execution": {"success": True},
        "violations": [],
    }
    summary = main_module.compact_summary(result)
    assert summary["tasks"] == 1
    assert summary["execution_plan_items"] == 1
    assert summary["graph_execution_success"] is True


def test_main_cli_success_json(monkeypatch, capsys):
    def fake_pipeline(**kwargs):
        assert kwargs["requirements"] == "Build API"
        assert kwargs["orchestrate_graph"] is True
        return {
            "success": True,
            "stage": "complete",
            "tasks": [],
            "execution_plan": [],
            "violations": [],
        }

    monkeypatch.setattr(main_module, "run_karpathy_pipeline", fake_pipeline)
    code = main_module.main(["--requirements", "Build API", "--orchestrate-graph", "--json"])
    output = json.loads(capsys.readouterr().out)
    assert code == 0
    assert output["success"] is True


def test_main_cli_failure_exit_code(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "run_karpathy_pipeline",
        lambda **kwargs: {"success": False, "stage": "complete", "tasks": [], "execution_plan": [], "violations": ["x"]},
    )
    assert main_module.main(["--requirements", "Broken"]) == 1
