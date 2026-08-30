"""Phase 0 domain + infra contract tests (no Docker required for schema tests)."""

from __future__ import annotations

from aip.domain.models import Evidence, Job, JobStatus, Run, ValidationOutcome, Workspace


def test_workspace_run_job_roundtrip() -> None:
    ws = Workspace(
        workspace_id="gpay",
        name="GPay",
        repo_scope=["n1shanthb/analytics-resume"],
    )
    job = Job(
        workspace_id=ws.workspace_id,
        job_type="github.create_issue",
        requested_action={"title": "x"},
        status=JobStatus.QUEUED,
    )
    run = Run(workspace_ids=[ws.workspace_id], jobs=[job], objectives=["smoke"])
    dumped = run.model_dump(mode="json")
    again = Run.model_validate(dumped)
    assert again.jobs[0].job_type == "github.create_issue"
    assert again.jobs[0].status == JobStatus.QUEUED


def test_validation_outcome_authority_verdict() -> None:
    outcome = ValidationOutcome(
        verdict="PASS",
        evidence=Evidence(job_type="gmail.send_email", refs={"message_id": "abc"}),
    )
    assert outcome.verdict == "PASS"
    assert outcome.evidence.refs["message_id"] == "abc"
