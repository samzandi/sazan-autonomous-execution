#!/usr/bin/env python3
"""Read-only GitHub repository inventory for Sazan Repo & Skill Steward.

The script never writes to GitHub. It discovers accessible repositories,
top-level capability markers, dependency manifests, and GitHub Actions
workflows. Private repository names are not persisted by this script.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API_VERSION = "2022-11-28"
DEFAULT_API = "https://api.github.com"

DEPENDENCY_MARKERS = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "pyproject.toml",
    "requirements.txt",
    "poetry.lock",
    "Pipfile",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "gradlew",
}

AGENT_MARKERS = {
    "AGENTS.md",
    "SKILL.md",
    "START_HERE.md",
}

TEST_MARKERS = {
    "tests",
    "test",
    "__tests__",
}


class GitHubClient:
    def __init__(self, token: str, api_base: str = DEFAULT_API) -> None:
        self.token = token
        self.api_base = api_base.rstrip("/")

    def get_json(self, path: str) -> Any:
        url = path if path.startswith("http") else f"{self.api_base}{path}"
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": "sazan-repo-skill-steward",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API error {exc.code}: {detail}") from exc

    def list_repositories(self) -> list[dict[str, Any]]:
        repos: list[dict[str, Any]] = []
        page = 1
        while True:
            query = urllib.parse.urlencode(
                {
                    "per_page": 100,
                    "page": page,
                    "sort": "updated",
                    "direction": "desc",
                    "affiliation": "owner,collaborator,organization_member",
                }
            )
            batch = self.get_json(f"/user/repos?{query}")
            if not isinstance(batch, list):
                raise RuntimeError("Unexpected GitHub repository response")
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return repos

    def list_contents(self, full_name: str, path: str = "") -> list[dict[str, Any]]:
        encoded_path = urllib.parse.quote(path.strip("/"), safe="/")
        suffix = f"/{encoded_path}" if encoded_path else ""
        payload = self.get_json(f"/repos/{full_name}/contents{suffix}")
        return payload if isinstance(payload, list) else []


def summarize_repository(client: GitHubClient, repo: dict[str, Any]) -> dict[str, Any]:
    full_name = str(repo.get("full_name", ""))
    root = client.list_contents(full_name)
    root_names = {str(item.get("name", "")) for item in root}

    workflows: list[str] = []
    if ".github" in root_names:
        try:
            github_items = client.list_contents(full_name, ".github")
            github_names = {str(item.get("name", "")) for item in github_items}
            if "workflows" in github_names:
                workflow_items = client.list_contents(full_name, ".github/workflows")
                workflows = sorted(
                    str(item.get("name", ""))
                    for item in workflow_items
                    if str(item.get("type", "")) == "file"
                )
        except RuntimeError:
            workflows = []

    return {
        "full_name": full_name,
        "visibility": repo.get("visibility", "private" if repo.get("private") else "public"),
        "archived": bool(repo.get("archived", False)),
        "fork": bool(repo.get("fork", False)),
        "default_branch": repo.get("default_branch"),
        "dependency_markers": sorted(root_names & DEPENDENCY_MARKERS),
        "agent_markers": sorted(root_names & AGENT_MARKERS),
        "has_tests": bool(root_names & TEST_MARKERS),
        "has_github_actions": bool(workflows),
        "workflows": workflows,
    }


def public_safe(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("visibility") == "private":
        safe = dict(record)
        safe["full_name"] = "<private-repository>"
        return safe
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only GitHub repository inventory for Sazan Repo & Skill Steward."
    )
    parser.add_argument(
        "--owner",
        help="Optional owner login. When set, only repositories owned by this login are included.",
    )
    parser.add_argument(
        "--public-safe",
        action="store_true",
        help="Redact private repository names in stdout.",
    )
    parser.add_argument(
        "--api-base",
        default=os.environ.get("GITHUB_API_URL", DEFAULT_API),
        help="GitHub API base URL.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is required.", file=sys.stderr)
        return 2

    client = GitHubClient(token=token, api_base=args.api_base)
    repos = client.list_repositories()

    if args.owner:
        owner = args.owner.casefold()
        repos = [
            repo
            for repo in repos
            if str(repo.get("owner", {}).get("login", "")).casefold() == owner
        ]

    output: list[dict[str, Any]] = []
    for repo in repos:
        full_name = str(repo.get("full_name", ""))
        try:
            record = summarize_repository(client, repo)
        except RuntimeError as exc:
            record = {
                "full_name": full_name,
                "visibility": repo.get(
                    "visibility", "private" if repo.get("private") else "public"
                ),
                "error": str(exc),
            }
        output.append(public_safe(record) if args.public_safe else record)

    print(json.dumps({"repositories": output}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
