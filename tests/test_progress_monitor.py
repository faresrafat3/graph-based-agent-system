from agents.progress_monitor import PROGRESS_MONITOR_PERMISSIONS, monitor_progress


def test_permissions_matrix():
    assert "execution_plan" in PROGRESS_MONITOR_PERMISSIONS["READ"]
    assert "progress_metrics" in PROGRESS_MONITOR_PERMISSIONS["WRITE"]
    assert "force_success" in PROGRESS_MONITOR_PERMISSIONS["NEVER"]


def test_monitor_progress_success():
    plan = [{"task_id": "task_1"}, {"task_id": "task_2"}]
    logs = [
        {"task_id": "task_1", "status": "completed", "timestamp": 1},
        {"task_id": "task_2", "status": "running", "duration_seconds": 10, "timestamp": 2},
    ]
    res = monitor_progress(plan, logs, timeout_seconds=30, thread_id="progress_success")
    assert res["success"] is True
    assert res["progress_metrics"]["completed_tasks"] == 1
    assert res["progress_metrics"]["running_tasks"] == 1


def test_monitor_progress_detects_stalled_and_failed():
    plan = [{"task_id": "task_1"}, {"task_id": "task_2"}]
    logs = [
        {"task_id": "task_1", "status": "running", "duration_seconds": 99},
        {"task_id": "task_2", "status": "failed"},
    ]
    res = monitor_progress(plan, logs, timeout_seconds=10, thread_id="progress_stalled")
    assert res["success"] is False
    assert res["stalled_tasks"] == ["task_1"]
    assert res["failed_tasks"] == ["task_2"]


def test_monitor_progress_validation_rules():
    """Verify various validation checks inside ProgressMonitorEngine"""
    plan = [{"task_id": "task_1"}, {"task_id": "task_2"}, {"task_id": "task_3"}]
    logs = [
        # Log missing task_id (Line 50)
        {"status": "running"},
        # Log referencing unknown task_id (Line 96)
        {"task_id": "task_unknown", "status": "completed"},
        # Task 1 exceeds timeout (stalled, Line 92)
        {"task_id": "task_1", "status": "running", "duration_seconds": 20},
        # Task 2 has unknown status, goes to pending (Line 106)
        {"task_id": "task_2", "status": "unknown"},
        # Task 3 has no logs, remains pending (Line 74-75)
    ]
    
    res = monitor_progress(plan, logs, timeout_seconds=10, thread_id="progress_validation_rules")
    assert res["success"] is False
    assert any("references unknown task id" in v for v in res["violations"])
    assert any("stalled after" in v for v in res["violations"])



def test_monitor_progress_invalid_type():
    """Verify defensive type check for non-list execution_plan inputs"""
    res = monitor_progress("not a list", [], thread_id="progress_invalid_type")
    assert res["success"] is False
    assert any("execution_plan must be a list" in v for v in res["violations"])

