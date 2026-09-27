"""GitHub App JWT → installation access token (comments appear as the app bot)."""

from __future__ import annotations

import time
from pathlib import Path
from threading import Lock
from typing import Any

import httpx

from aip.config import ROOT, settings

_lock = Lock()
_cached_token: str | None = None
_cached_expires_at: float = 0.0


def github_app_configured() -> bool:
    return bool(
        (settings.github_app_id or "").strip()
        and (settings.github_app_installation_id or "").strip()
        and _private_key_pem()
    )


def github_app_installed() -> tuple[bool, str]:
    """Return whether the configured GitHub App installation token can be minted."""
    if not github_app_configured():
        return False, "GitHub App ID, installation ID, or private key is missing"
    try:
        get_installation_token()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:200]
    return True, ""


def resolve_github_token() -> str | None:
    """Prefer GitHub App installation token; fall back to personal GITHUB_TOKEN."""
    if github_app_configured():
        try:
            return get_installation_token()
        except Exception:  # noqa: BLE001
            # Fall through to PAT if app auth fails
            pass
    token = (settings.github_token or "").strip()
    return token or None


def get_installation_token() -> str:
    global _cached_token, _cached_expires_at
    now = time.time()
    with _lock:
        if _cached_token and now < (_cached_expires_at - 60):
            return _cached_token

    jwt_token = _build_app_jwt()
    installation_id = (settings.github_app_installation_id or "").strip()
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, headers=headers)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"GitHub App installation token failed ({resp.status_code}): "
                f"{resp.text[:400]}"
            )
        data: dict[str, Any] = resp.json()
    token = str(data.get("token") or "")
    if not token:
        raise RuntimeError("GitHub App installation token response missing token")
    # Tokens typically expire in ~1 hour
    expires_at = now + 3600
    exp_raw = data.get("expires_at")
    if isinstance(exp_raw, str) and exp_raw:
        try:
            from datetime import datetime

            expires_at = datetime.fromisoformat(
                exp_raw.replace("Z", "+00:00")
            ).timestamp()
        except ValueError:
            pass
    with _lock:
        _cached_token = token
        _cached_expires_at = expires_at
    return token


def _private_key_pem() -> str | None:
    inline = (settings.github_app_private_key or "").strip()
    if inline:
        return inline.replace("\\n", "\n")
    path_raw = (settings.github_app_private_key_path or "").strip()
    if not path_raw:
        return None
    path = Path(path_raw)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _build_app_jwt() -> str:
    try:
        import jwt
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "PyJWT is required for GitHub App auth. pip install 'PyJWT[crypto]'"
        ) from exc

    app_id = (settings.github_app_id or "").strip()
    pem = _private_key_pem()
    if not app_id or not pem:
        raise RuntimeError("GitHub App ID or private key is not configured")

    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (9 * 60),
        "iss": app_id,
    }
    return jwt.encode(payload, pem, algorithm="RS256")


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "agentsuite-v2",
    }


def find_pull_request_number(
    *,
    owner: str,
    repo: str,
    sha: str = "",
    head_branch: str = "",
) -> int | None:
    """Resolve a PR number when workflow_run.pull_requests is empty (common)."""
    token = resolve_github_token()
    if not token or not owner or not repo:
        return None
    headers = _github_headers(token)
    with httpx.Client(timeout=30.0) as client:
        sha_value = (sha or "").strip()
        if sha_value:
            url = (
                f"https://api.github.com/repos/{owner}/{repo}/commits/"
                f"{sha_value}/pulls"
            )
            resp = client.get(url, headers=headers)
            if resp.status_code < 400:
                rows = resp.json()
                if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                    number = rows[0].get("number")
                    if number is not None:
                        return int(number)

        branch = (head_branch or "").strip()
        if branch:
            url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
            resp = client.get(
                url,
                headers=headers,
                params={"state": "open", "head": f"{owner}:{branch}", "per_page": 5},
            )
            if resp.status_code < 400:
                rows = resp.json()
                if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                    number = rows[0].get("number")
                    if number is not None:
                        return int(number)
    return None


def get_pull_request_context(
    *,
    owner: str,
    repo: str,
    pull_number: int,
) -> dict[str, Any]:
    """Read-only PR facts for review drafting (title, body, files, diff stats)."""
    token = resolve_github_token()
    if not token:
        return {"error": "GitHub auth missing"}
    headers = _github_headers(token)
    base = f"https://api.github.com/repos/{owner}/{repo}"
    out: dict[str, Any] = {"owner": owner, "repo": repo, "pull_number": int(pull_number)}
    with httpx.Client(timeout=45.0) as client:
        pr_resp = client.get(f"{base}/pulls/{int(pull_number)}", headers=headers)
        if pr_resp.status_code >= 400:
            return {"error": f"PR fetch failed ({pr_resp.status_code}): {pr_resp.text[:300]}"}
        pr = pr_resp.json() if isinstance(pr_resp.json(), dict) else {}
        user = pr.get("user") if isinstance(pr.get("user"), dict) else {}
        head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
        base_ref = pr.get("base") if isinstance(pr.get("base"), dict) else {}
        out.update(
            {
                "title": str(pr.get("title") or ""),
                "body": str(pr.get("body") or ""),
                "state": str(pr.get("state") or ""),
                "html_url": str(pr.get("html_url") or ""),
                "author": str(user.get("login") or ""),
                "head_branch": str(head.get("ref") or ""),
                "base_branch": str(base_ref.get("ref") or ""),
                "additions": int(pr.get("additions") or 0),
                "deletions": int(pr.get("deletions") or 0),
                "changed_files": int(pr.get("changed_files") or 0),
                "commits": int(pr.get("commits") or 0),
            }
        )
        files_resp = client.get(
            f"{base}/pulls/{int(pull_number)}/files",
            headers=headers,
            params={"per_page": 30},
        )
        files: list[dict[str, str]] = []
        if files_resp.status_code < 400 and isinstance(files_resp.json(), list):
            for row in files_resp.json():
                if not isinstance(row, dict):
                    continue
                files.append(
                    {
                        "filename": str(row.get("filename") or ""),
                        "status": str(row.get("status") or ""),
                        "additions": str(row.get("additions") or "0"),
                        "deletions": str(row.get("deletions") or "0"),
                        "patch": str(row.get("patch") or "")[:1200],
                    }
                )
        out["files"] = files
    return out


def get_issue_context(
    *,
    owner: str,
    repo: str,
    number: int,
) -> dict[str, Any]:
    """Read-only issue facts for comment drafting."""
    token = resolve_github_token()
    if not token:
        return {"error": "GitHub auth missing"}
    headers = _github_headers(token)
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{int(number)}"
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, headers=headers)
        if resp.status_code >= 400:
            return {"error": f"Issue fetch failed ({resp.status_code}): {resp.text[:300]}"}
        issue = resp.json() if isinstance(resp.json(), dict) else {}
    user = issue.get("user") if isinstance(issue.get("user"), dict) else {}
    labels = [
        str(lab.get("name") or "")
        for lab in (issue.get("labels") or [])
        if isinstance(lab, dict) and lab.get("name")
    ]
    return {
        "owner": owner,
        "repo": repo,
        "issue_number": int(number),
        "title": str(issue.get("title") or ""),
        "body": str(issue.get("body") or ""),
        "state": str(issue.get("state") or ""),
        "html_url": str(issue.get("html_url") or ""),
        "author": str(user.get("login") or ""),
        "labels": labels,
        "is_pull_request": "pull_request" in (issue.get("pull_request") or {}),
    }


def create_issue(
    *,
    owner: str,
    repo: str,
    title: str,
    body: str,
) -> dict[str, Any]:
    """Open an issue as the GitHub App (or PAT)."""
    token = resolve_github_token()
    if not token:
        raise RuntimeError("GitHub auth missing for create issue")
    text = (body or "").strip()
    headline = (title or "").strip() or "CI failure"
    if len(text) > 65000:
        text = text[:65000] + "\n\n…"
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            url,
            headers=_github_headers(token),
            json={"title": headline[:240], "body": text},
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"GitHub create issue failed ({resp.status_code}): {resp.text[:400]}"
            )
        data = resp.json()
    return data if isinstance(data, dict) else {"ok": True}


def post_issue_comment(
    *,
    owner: str,
    repo: str,
    number: int,
    body: str,
) -> dict[str, Any]:
    """Post an issue/PR conversation comment as the GitHub App (or PAT)."""
    token = resolve_github_token()
    if not token:
        raise RuntimeError("GitHub auth missing for issue comment")
    text = (body or "").strip()
    if not text:
        raise ValueError("comment body is empty")
    if len(text) > 65000:
        text = text[:65000] + "\n\n…"
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{int(number)}/comments"
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            url, headers=_github_headers(token), json={"body": text}
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"GitHub comment failed ({resp.status_code}): {resp.text[:400]}"
            )
        data = resp.json()
    return data if isinstance(data, dict) else {"ok": True}


def list_issue_comments(
    *,
    owner: str,
    repo: str,
    number: int,
    per_page: int = 30,
) -> list[dict[str, Any]]:
    """List recent issue/PR conversation comments."""
    token = resolve_github_token()
    if not token:
        raise RuntimeError("GitHub auth missing for listing comments")
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{int(number)}/comments"
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(
            url,
            headers=_github_headers(token),
            params={"per_page": max(1, min(per_page, 100))},
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"GitHub list comments failed ({resp.status_code}): {resp.text[:400]}"
            )
        data = resp.json()
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def create_pull_request_review(
    *,
    owner: str,
    repo: str,
    pull_number: int,
    body: str,
    event: str = "COMMENT",
) -> dict[str, Any]:
    """Submit a PR review (COMMENT / APPROVE / REQUEST_CHANGES)."""
    token = resolve_github_token()
    if not token:
        raise RuntimeError("GitHub auth missing for PR review")
    text = (body or "").strip()
    if not text:
        raise ValueError("PR review body is empty")
    ev = (event or "COMMENT").strip().upper()
    if ev not in ("COMMENT", "APPROVE", "REQUEST_CHANGES", "PENDING"):
        ev = "COMMENT"
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{int(pull_number)}/reviews"
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            url,
            headers=_github_headers(token),
            json={"body": text[:65000], "event": ev},
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"GitHub PR review failed ({resp.status_code}): {resp.text[:400]}"
            )
        data = resp.json()
    return data if isinstance(data, dict) else {"ok": True}


def create_or_update_repo_file(
    *,
    owner: str,
    repo: str,
    path: str,
    content: str,
    message: str,
    branch: str | None = None,
) -> dict[str, Any]:
    """Create or update a file via Contents API (used for CI workflow writes)."""
    import base64

    token = resolve_github_token()
    if not token:
        raise RuntimeError("GitHub auth missing for file write")
    file_path = (path or "").lstrip("/")
    if not file_path:
        raise ValueError("path required")
    api = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
    headers = _github_headers(token)
    sha = None
    with httpx.Client(timeout=30.0) as client:
        get_params = {"ref": branch} if branch else None
        existing = client.get(api, headers=headers, params=get_params)
        if existing.status_code < 400:
            body = existing.json()
            if isinstance(body, dict) and body.get("sha"):
                sha = str(body["sha"])
        payload: dict[str, Any] = {
            "message": (message or f"Update {file_path}")[:240],
            "content": base64.b64encode((content or "").encode("utf-8")).decode("ascii"),
        }
        if sha:
            payload["sha"] = sha
        if branch:
            payload["branch"] = branch
        resp = client.put(api, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"GitHub contents write failed ({resp.status_code}): {resp.text[:400]}"
            )
        data = resp.json()
    return data if isinstance(data, dict) else {"ok": True}
