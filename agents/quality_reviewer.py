"""
Quality Reviewer Agent - Deterministic global quality gate.

Karpathy Meta-Agent #4. Aggregates validation, assignment, dispatch, and
execution evidence into one approval/rejection decision without LLM calls.
"""

from typing import Any, TypedDict

from kernel.karpathy_loop import build_karpathy_loop


QUALITY_REVIEWER_PERMISSIONS = {
    "READ": ["validation_reports", "execution_results", "acceptance_criteria", "security_reports"],
    "WRITE": ["approval_status", "quality_report", "rejection_reasons"],
    "NEVER": ["bypass_tests", "force_commit_failed_code", "modify_artifacts"],
    "HUMAN_CHECKPOINT": ["critical_quality_gate_failure"],
}


class QualityReviewerState(TypedDict):
    validation_reports: list[dict]
    assignment_result: dict
    dispatch_result: dict
    execution_results: list[dict]
    acceptance_criteria: list[str]
    security_reports: list[dict]
    quality_report: dict
    rejection_reasons: list[str]
    quality_score: float
    approved: bool
    retry_count: int
    success: bool


class QualityReviewerEngine:
    """Deterministic quality scoring and approval checks."""

    @staticmethod
    def _is_successful(report: dict) -> bool:
        return bool(report.get("success", report.get("passed", report.get("approved", False))))

    @classmethod
    def review(
        cls,
        validation_reports: list[dict],
        assignment_result: dict,
        dispatch_result: dict,
        execution_results: list[dict],
        acceptance_criteria: list[str],
        security_reports: list[dict],
    ) -> dict[str, Any]:
        """Compute a deterministic approval decision and quality score."""
        if not isinstance(validation_reports, list):
            return {
                "approved": False,
                "success": False,
                "quality_score": 0.0,
                "rejection_reasons": ["validation_reports must be a list."],
            }
        if not isinstance(execution_results, list):
            return {
                "approved": False,
                "success": False,
                "quality_score": 0.0,
                "rejection_reasons": ["execution_results must be a list."],
            }
        if not isinstance(security_reports, list):
            return {
                "approved": False,
                "success": False,
                "quality_score": 0.0,
                "rejection_reasons": ["security_reports must be a list."],
            }

        reasons = []
        checks = []

        for idx, report in enumerate(validation_reports or [], 1):
            ok = cls._is_successful(report)
            checks.append(ok)
            if not ok:
                reasons.append(f"Validation report {idx} failed: {report.get('breaches', report)}")

        if assignment_result:
            ok = cls._is_successful(assignment_result)
            checks.append(ok)
            if not ok:
                reasons.append(f"Assignment failed: {assignment_result.get('breaches', [])}")

        if dispatch_result and dispatch_result.get("results"):
            ok = cls._is_successful(dispatch_result)
            checks.append(ok)
            if not ok:
                reasons.append(f"Domain dispatch failed: {dispatch_result.get('breaches', [])}")

        for idx, result in enumerate(execution_results or [], 1):
            ok = cls._is_successful(result)
            checks.append(ok)
            if not ok:
                reasons.append(f"Execution result {idx} failed at stage '{result.get('stage')}': {result.get('error')}")

        for idx, report in enumerate(security_reports or [], 1):
            severity = str(report.get("severity", "")).lower()
            ok = cls._is_successful(report) and severity != "critical"
            checks.append(ok)
            if not ok:
                reasons.append(f"Security report {idx} blocks approval: {report}")

        if acceptance_criteria is not None:
            ok = all(isinstance(item, str) and item.strip() for item in acceptance_criteria)
            checks.append(ok)
            if not ok:
                reasons.append("Acceptance criteria are missing or empty.")

        if not checks:
            checks.append(False)
            reasons.append("No quality evidence was provided.")

        quality_score = round(sum(1 for ok in checks if ok) / len(checks), 4)
        approved = quality_score == 1.0 and not reasons
        return {
            "approved": approved,
            "success": approved,
            "quality_score": quality_score,
            "rejection_reasons": reasons,
            "quality_report": {
                "total_checks": len(checks),
                "passed_checks": sum(1 for ok in checks if ok),
                "failed_checks": sum(1 for ok in checks if not ok),
            },
        }


# Karpathy Loop (shared factory; standard nodes, approval-driven evaluate)

def execute(state: QualityReviewerState) -> dict:
    """Step 2: Execute - compute deterministic quality decision."""
    return QualityReviewerEngine.review(
        validation_reports=state.get("validation_reports", []),
        assignment_result=state.get("assignment_result", {}),
        dispatch_result=state.get("dispatch_result", {}),
        execution_results=state.get("execution_results", []),
        acceptance_criteria=state.get("acceptance_criteria", []),
        security_reports=state.get("security_reports", []),
    )


def evaluate(state: QualityReviewerState) -> dict:
    """Step 3: Evaluate - approval is the success condition."""
    return {"success": bool(state.get("approved", False))}


quality_reviewer_graph = build_karpathy_loop(
    QualityReviewerState,
    execute_fn=execute,
    evaluate_fn=evaluate,
    list_input_keys=("validation_reports", "execution_results", "acceptance_criteria", "security_reports"),
)


def review_quality(
    validation_reports: list[dict] | None = None,
    assignment_result: dict | None = None,
    dispatch_result: dict | None = None,
    execution_results: list[dict] | None = None,
    acceptance_criteria: list[str] | None = None,
    security_reports: list[dict] | None = None,
    thread_id: str = "quality_reviewer_session",
) -> dict[str, Any]:
    """Run deterministic global quality review."""
    result = quality_reviewer_graph.invoke(
        {
            "validation_reports": validation_reports or [],
            "assignment_result": assignment_result or {},
            "dispatch_result": dispatch_result or {},
            "execution_results": execution_results or [],
            "acceptance_criteria": acceptance_criteria or [],
            "security_reports": security_reports or [],
            "quality_report": {},
            "rejection_reasons": [],
            "quality_score": 0.0,
            "approved": False,
            "retry_count": 0,
            "success": False,
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    return {
        "success": result.get("success", False),
        "approved": result.get("approved", False),
        "quality_score": result.get("quality_score", 0.0),
        "quality_report": result.get("quality_report", {}),
        "rejection_reasons": result.get("rejection_reasons", []),
    }
