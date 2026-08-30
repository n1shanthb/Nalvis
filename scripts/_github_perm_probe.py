"""Safe GitHub permission probe — App vs PAT (no destructive deletes)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

load_dotenv()

from aip.config import settings
from aip.integrations.github_app import (
    get_installation_token,
    github_app_configured,
    _github_headers,
)


def probe(label: str, token: str | None) -> dict:
    out: dict = {"label": label, "token_present": bool(token)}
    if not token:
        return out
    o, r = settings.smoke_github_owner, settings.smoke_github_repo
    h = _github_headers(token)
    with httpx.Client(timeout=30.0) as c:
        u = c.get("https://api.github.com/user", headers=h)
        out["user_status"] = u.status_code
        if u.status_code < 400 and isinstance(u.json(), dict):
            out["login"] = u.json().get("login")
        out["x_oauth_scopes"] = u.headers.get("x-oauth-scopes")
        out["x_accepted_oauth_scopes"] = u.headers.get("x-accepted-oauth-scopes")

        inst = c.get("https://api.github.com/installation/repositories", headers=h)
        out["install_repos_status"] = inst.status_code
        if inst.status_code < 400:
            repos = (inst.json() or {}).get("repositories") or []
            out["install_repos"] = [
                {"full_name": rr.get("full_name"), "permissions": rr.get("permissions")}
                for rr in repos[:10]
            ]

        repo = c.get(f"https://api.github.com/repos/{o}/{r}", headers=h)
        out["repo_status"] = repo.status_code
        if repo.status_code < 400:
            out["repo_permissions"] = (repo.json() or {}).get("permissions")

        pulls = c.get(
            f"https://api.github.com/repos/{o}/{r}/pulls",
            headers=h,
            params={"state": "open", "per_page": 3},
        )
        out["list_pulls"] = pulls.status_code
        if pulls.status_code < 400:
            out["open_prs"] = [p.get("number") for p in pulls.json() if isinstance(p, dict)]

        # Non-destructive write probes (tiny COMMENT review / tiny contents update)
        # Prefer dry-run style: attempt then report status only
        prs = out.get("open_prs") or [2]
        prn = int(prs[0])
        rev = c.post(
            f"https://api.github.com/repos/{o}/{r}/pulls/{prn}/reviews",
            headers=h,
            json={
                "body": f"[agentsuite probe] review capability check {datetime.now(timezone.utc).isoformat()}",
                "event": "COMMENT",
            },
        )
        out["review_pr"] = {
            "status": rev.status_code,
            "body": rev.text[:200],
            "ok": rev.status_code < 400,
            "id": (rev.json() or {}).get("id") if rev.status_code < 400 else None,
            "html_url": (rev.json() or {}).get("html_url") if rev.status_code < 400 else None,
        }

        # Contents: read existing ship smoke workflow if any, else try create tiny file
        path = ".github/workflows/agentsuite-ship-smoke.yml"
        getc = c.get(f"https://api.github.com/repos/{o}/{r}/contents/{path}", headers=h)
        out["get_workflow"] = getc.status_code
        sha = None
        if getc.status_code < 400 and isinstance(getc.json(), dict):
            sha = getc.json().get("sha")
        import base64

        content = (
            "name: agentsuite-ship-smoke\n"
            "on:\n  workflow_dispatch:\n"
            "jobs:\n  ping:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: echo agentsuite-probe\n"
        )
        payload = {
            "message": f"[agentsuite probe] workflow capability {datetime.now(timezone.utc).isoformat()}",
            "content": base64.b64encode(content.encode()).decode("ascii"),
        }
        if sha:
            payload["sha"] = sha
        put = c.put(
            f"https://api.github.com/repos/{o}/{r}/contents/{path}",
            headers=h,
            json=payload,
        )
        out["contents_write"] = {
            "status": put.status_code,
            "body": put.text[:200],
            "ok": put.status_code < 400,
            "sha": ((put.json() or {}).get("commit") or {}).get("sha")
            if put.status_code < 400
            else None,
            "html_url": ((put.json() or {}).get("content") or {}).get("html_url")
            if put.status_code < 400
            else None,
        }

        # Issue comment on PR (sometimes allowed when formal review isn't)
        ic = c.post(
            f"https://api.github.com/repos/{o}/{r}/issues/{prn}/comments",
            headers=h,
            json={"body": f"[agentsuite probe] issue-comment {datetime.now(timezone.utc).isoformat()}"},
        )
        out["issue_comment"] = {
            "status": ic.status_code,
            "ok": ic.status_code < 400,
            "body": ic.text[:160],
        }
    return out


def main() -> None:
    results = {
        "app_configured": github_app_configured(),
        "smoke": f"{settings.smoke_github_owner}/{settings.smoke_github_repo}",
    }
    app_tok = None
    if github_app_configured():
        try:
            app_tok = get_installation_token()
            # Also dump installation permissions from create token response path
            from aip.integrations.github_app import _build_app_jwt

            jwt = _build_app_jwt()
            with httpx.Client(timeout=30.0) as c:
                resp = c.get(
                    f"https://api.github.com/app/installations/{settings.github_app_installation_id}",
                    headers={
                        "Authorization": f"Bearer {jwt}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )
                if resp.status_code < 400:
                    data = resp.json()
                    results["installation_permissions"] = data.get("permissions")
                    results["installation_account"] = (data.get("account") or {}).get("login")
                    results["repository_selection"] = data.get("repository_selection")
        except Exception as exc:  # noqa: BLE001
            results["app_token_error"] = str(exc)[:300]

    results["APP"] = probe("APP", app_tok)
    results["PAT"] = probe("PAT", (settings.github_token or "").strip() or None)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
