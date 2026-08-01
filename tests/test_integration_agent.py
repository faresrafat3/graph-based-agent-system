from agents.integration_agent import INTEGRATION_AGENT_PERMISSIONS, integrate_artifacts


def test_permissions_matrix():
    assert "software_agent_artifacts" in INTEGRATION_AGENT_PERMISSIONS["READ"]
    assert "integration_manifest" in INTEGRATION_AGENT_PERMISSIONS["WRITE"]
    assert "deploy_untested_bundle" in INTEGRATION_AGENT_PERMISSIONS["NEVER"]


def test_integrate_artifacts_success():
    artifacts = [
        {
            "filename": "auth.py",
            "code": "def login(): pass",
            "test_filename": "test_auth.py",
            "test_code": "def test_login(): pass",
            "exports": ["login"],
        }
    ]
    res = integrate_artifacts(artifacts, thread_id="integration_success")
    assert res["success"] is True
    assert res["integration_manifest"]["modules"] == ["auth.py"]
    assert res["integration_manifest"]["exports"]["login"] == "auth.py"


def test_integrate_artifacts_detects_duplicate_filename_and_export():
    artifacts = [
        {"filename": "a.py", "code": "", "exports": ["run"]},
        {"filename": "a.py", "code": "", "exports": ["run"]},
    ]
    res = integrate_artifacts(artifacts, thread_id="integration_conflict")
    assert res["success"] is False
    assert any("Duplicate artifact filename" in c for c in res["conflicts"])
    assert any("Duplicate export" in c for c in res["conflicts"])
