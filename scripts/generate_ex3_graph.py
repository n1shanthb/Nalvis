"""Generate ex3.json — ex1-format KG with 2 projects + GitHub/Gmail/Calendar/AWS."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "ex3.json"
GROUP = "heliostack"


def nid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def node(
    id_: str,
    name: str,
    *,
    val: int = 3,
    type_: str = "Entity",
    source_id: str | None = "upload",
    source_type: str | None = "upload",
    need_attention: bool = False,
    summary: str,
) -> dict:
    return {
        "id": id_,
        "name": name,
        "val": val,
        "type": type_,
        "group_id": GROUP,
        "source_id": source_id,
        "source_type": source_type,
        "need_attention": need_attention,
        "summary": summary,
    }


def link(source: str, target: str, relation_type: str, *, source_id=None, source_type=None) -> dict:
    return {
        "source": source,
        "target": target,
        "relation_type": relation_type,
        "group_id": GROUP,
        "source_id": source_id,
        "source_type": source_type,
    }


def main() -> None:
    # Stable ids for readability in tests/docs
    company = "c0000001-0000-4000-8000-000000000001"
    proj_resume = "p0000001-0000-4000-8000-000000000001"
    proj_ops = "p0000002-0000-4000-8000-000000000002"
    repo_resume = "r0000001-0000-4000-8000-000000000001"
    repo_ops = "r0000002-0000-4000-8000-000000000002"
    github_tool = "s0000001-0000-4000-8000-000000000001"
    gmail_tool = "s0000002-0000-4000-8000-000000000002"
    calendar_tool = "s0000003-0000-4000-8000-000000000003"
    aws_tool = "s0000004-0000-4000-8000-000000000004"
    email_releases = "m0000001-0000-4000-8000-000000000001"
    email_alerts = "m0000002-0000-4000-8000-000000000002"
    email_customer = "m0000003-0000-4000-8000-000000000003"
    cal_sprint = "cal00001-0000-4000-8000-000000000001"
    cal_release = "cal00002-0000-4000-8000-000000000002"
    cal_standup = "cal00003-0000-4000-8000-000000000003"
    aws_account = "aws00001-0000-4000-8000-000000000001"
    aws_s3 = "aws00002-0000-4000-8000-000000000002"
    aws_lambda = "aws00003-0000-4000-8000-000000000003"
    person_pm = "u0000001-0000-4000-8000-000000000001"
    person_eng = "u0000002-0000-4000-8000-000000000002"

    gh_src = "github:repo:heliostack-main"
    gh = {"source_id": gh_src, "source_type": "github"}

    nodes = [
        node(
            company,
            "HelioStack Inc",
            val=18,
            type_="organization",
            summary=(
                "HelioStack Inc builds analytics and internal automation products. "
                "The company standardizes on GitHub for source control, Gmail for customer and ops comms, "
                "Google Calendar for release planning, and AWS for cloud infrastructure. "
                "Two active product lines: Resume Analytics and Ops Console."
            ),
        ),
        node(
            proj_resume,
            "Resume Analytics",
            val=12,
            type_="project",
            summary=(
                "Resume Analytics is a customer-facing resume scoring product. "
                "Primary repo: github.com/n1shanthb/analytics-resume. "
                "Uses Gmail list eng-releases@heliostack.io for release announcements "
                "and calendar Sprint Planning for bi-weekly planning."
            ),
        ),
        node(
            proj_ops,
            "Ops Console",
            val=12,
            type_="project",
            summary=(
                "Ops Console is the internal agentic operations dashboard. "
                "Primary repo: github.com/heliostack/ops-console. "
                "Uses Gmail ops-alerts@heliostack.io for on-call threads "
                "and calendar Release Review for weekly ship reviews."
            ),
        ),
        node(
            repo_resume,
            "analytics-resume",
            val=9,
            source_id=gh_src,
            source_type="github",
            summary=(
                "GitHub repository n1shanthb/analytics-resume — clone from "
                "github.com/n1shanthb/analytics-resume.git. "
                "Resume Analytics backend and scoring pipeline. "
                "Issues and PRs tracked via GitHub MCP."
            ),
        ),
        node(
            repo_ops,
            "ops-console",
            val=9,
            source_id=gh_src,
            source_type="github",
            summary=(
                "GitHub repository heliostack/ops-console — clone from "
                "github.com/heliostack/ops-console.git. "
                "React ops console wired to AgentSuite control plane APIs."
            ),
        ),
        node(
            github_tool,
            "GitHub",
            val=6,
            summary=(
                "Company-wide GitHub MCP integration for issues, PRs, and repo automation. "
                "Used by both Resume Analytics and Ops Console projects."
            ),
        ),
        node(
            gmail_tool,
            "Gmail",
            val=6,
            summary=(
                "Native Gmail OAuth integration for outbound mail and inbound webhook signals. "
                "Distribution lists: eng-releases@heliostack.io and ops-alerts@heliostack.io."
            ),
        ),
        node(
            calendar_tool,
            "Google Calendar",
            val=5,
            summary=(
                "Native Google Calendar integration for sprint planning, release reviews, "
                "and standups across both product teams."
            ),
        ),
        node(
            aws_tool,
            "AWS",
            val=7,
            summary=(
                "AWS account 123456789012 hosts S3 artifact storage and Lambda deploy runners. "
                "Not yet wired as an executable AgentSuite connector in v1 — discovery only."
            ),
        ),
        node(
            email_releases,
            "eng-releases@heliostack.io",
            val=4,
            type_="email",
            source_type="mail",
            summary=(
                "Release announcement mailing list for Resume Analytics. "
                "Contact: nishanth@heliostack.io. "
                "Recommended automation: GmailCommsAgent sends release notes after GitHub tag."
            ),
        ),
        node(
            email_alerts,
            "ops-alerts@heliostack.io",
            val=4,
            type_="email",
            source_type="mail",
            summary=(
                "On-call and incident thread list for Ops Console. "
                "Contact: priya@heliostack.io."
            ),
        ),
        node(
            email_customer,
            "Customer onboarding delay",
            val=6,
            type_="email",
            source_type="mail",
            need_attention=True,
            summary=(
                "Inbound Gmail thread from customer@example.com: onboarding API latency blocking launch. "
                "Recommended agent: GitHubIssueManagerAgent to track fix in "
                "github.com/n1shanthb/analytics-resume. "
                "Also schedule follow-up on Google Calendar."
            ),
        ),
        node(
            cal_sprint,
            "Sprint Planning — Resume Analytics",
            val=3,
            type_="meeting",
            source_type="calendar",
            summary=(
                "Bi-weekly sprint planning calendar event for Resume Analytics. "
                "Attendees: nishanth@heliostack.io, priya@heliostack.io. "
                "CalendarSchedulerAgent can book follow-ups."
            ),
        ),
        node(
            cal_release,
            "Release Review — Ops Console",
            val=3,
            type_="meeting",
            source_type="calendar",
            summary=(
                "Weekly release review for Ops Console on Google Calendar. "
                "Links GitHub PRs from heliostack/ops-console to ship checklist."
            ),
        ),
        node(
            cal_standup,
            "HelioStack Engineering Standup",
            val=2,
            type_="meeting",
            source_type="calendar",
            summary="Daily standup for both Resume Analytics and Ops Console teams.",
        ),
        node(
            aws_account,
            "AWS Account 123456789012",
            val=5,
            type_="Entity",
            summary=(
                "Primary AWS account for HelioStack. Region us-east-1. "
                "Hosts S3 and Lambda resources for both projects."
            ),
        ),
        node(
            aws_s3,
            "heliostack-artifacts",
            val=4,
            type_="Entity",
            summary=(
                "S3 bucket heliostack-artifacts in AWS account 123456789012. "
                "Stores build artifacts from github.com/heliostack/ops-console CI."
            ),
        ),
        node(
            aws_lambda,
            "deploy-runner",
            val=4,
            type_="Entity",
            need_attention=True,
            summary=(
                "AWS Lambda function deploy-runner packages releases to S3. "
                "Automation opportunity: unsupported AWS deploy agent until connector ships."
            ),
        ),
        node(
            person_pm,
            "Nishanth B",
            val=3,
            type_="person",
            summary="Product owner for Resume Analytics. Email: nishanth@heliostack.io.",
        ),
        node(
            person_eng,
            "Priya K",
            val=3,
            type_="person",
            summary="Engineering lead for Ops Console. Email: priya@heliostack.io.",
        ),
    ]

    links = [
        link(proj_resume, company, "BELONGS_TO"),
        link(proj_ops, company, "BELONGS_TO"),
        link(repo_resume, proj_resume, "BELONGS_TO", **gh),
        link(repo_ops, proj_ops, "BELONGS_TO", **gh),
        link(proj_resume, github_tool, "USES", **gh),
        link(proj_ops, github_tool, "USES", **gh),
        link(proj_resume, gmail_tool, "USES"),
        link(proj_ops, gmail_tool, "USES"),
        link(proj_resume, calendar_tool, "USES"),
        link(proj_ops, calendar_tool, "USES"),
        link(company, aws_tool, "USES"),
        link(email_releases, proj_resume, "BELONGS_TO"),
        link(email_alerts, proj_ops, "BELONGS_TO"),
        link(email_customer, proj_resume, "RELATED_TO"),
        link(cal_sprint, proj_resume, "SCHEDULED_FOR"),
        link(cal_release, proj_ops, "SCHEDULED_FOR"),
        link(cal_standup, company, "SCHEDULED_FOR"),
        link(aws_account, company, "OWNED_BY"),
        link(aws_s3, aws_account, "PART_OF"),
        link(aws_lambda, aws_account, "PART_OF"),
        link(aws_s3, repo_ops, "STORES_ARTIFACTS_FROM", **gh),
        link(person_pm, proj_resume, "OWNS"),
        link(person_eng, proj_ops, "OWNS"),
        link(person_pm, email_releases, "SUBSCRIBED_TO"),
        link(person_eng, email_alerts, "SUBSCRIBED_TO"),
        link(email_customer, repo_resume, "REFERENCES", **gh),
        link(cal_release, repo_ops, "TRACKS", **gh),
    ]

    payload = {"company": "HelioStack Inc", "nodes": nodes, "links": links}
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({len(nodes)} nodes, {len(links)} links)")


if __name__ == "__main__":
    main()
