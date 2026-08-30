"""Routing auditor + smoke/app allowlist helpers."""

from __future__ import annotations

from unittest.mock import patch

from aip.director.auditor import extra_github_repos_outside_kg


def test_extra_github_repos_outside_kg_lowercases() -> None:
    with patch("aip.config.settings") as settings:
        settings.smoke_github_owner = "Acme"
        settings.smoke_github_repo = "App"
        settings.smoke_github_app_repo = "N1shanthb/Nalvis-Landing"
        assert extra_github_repos_outside_kg() == {
            "acme/app",
            "n1shanthb/nalvis-landing",
        }


def test_extra_github_repos_empty_when_unset() -> None:
    with patch("aip.config.settings") as settings:
        settings.smoke_github_owner = ""
        settings.smoke_github_repo = ""
        settings.smoke_github_app_repo = ""
        assert extra_github_repos_outside_kg() == set()
