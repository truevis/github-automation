#!/usr/bin/env python3
"""Update collaborators across GitHub repositories matching a prefix."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_OWNER = "truevis"
DEFAULT_PREFIX = "bse-"
DEFAULT_REMOVE_USER = "BSE-Jared"
DEFAULT_ADD_USER = "BSE-Git"
DEFAULT_PERMISSION = "push"
API_BASE = "https://api.github.com"


@dataclass
class ApiResponse:
    status: int
    body: Any


class GitHubApi:
    def __init__(self, token: str) -> None:
        self.token = token

    def request(self, method: str, path: str, data: dict[str, Any] | None = None) -> ApiResponse:
        body_bytes = None
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        if data is not None:
            body_bytes = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{API_BASE}{path}",
            data=body_bytes,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(request) as response:
                return ApiResponse(response.status, self._read_json(response.read()))
        except urllib.error.HTTPError as error:
            return ApiResponse(error.code, self._read_json(error.read()))

    @staticmethod
    def _read_json(raw_body: bytes) -> Any:
        if not raw_body:
            return None

        text = raw_body.decode("utf-8", errors="replace")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove one GitHub collaborator and add another across repositories."
    )
    parser.add_argument("--owner", default=DEFAULT_OWNER, help="GitHub owner or org name.")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX, help="Repository name prefix to match.")
    parser.add_argument(
        "--repo",
        action="append",
        help="Specific repository name to update. Can be passed more than once. Skips prefix discovery.",
    )
    parser.add_argument("--remove-user", default=DEFAULT_REMOVE_USER, help="Collaborator username to remove.")
    parser.add_argument("--add-user", default=DEFAULT_ADD_USER, help="Collaborator username to add.")
    parser.add_argument(
        "--permission",
        default=DEFAULT_PERMISSION,
        choices=("pull", "triage", "push", "maintain", "admin"),
        help="Permission to grant to the added collaborator.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually make collaborator changes. Without this flag, the script only prints what it would do.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum repositories to fetch when discovering by prefix.",
    )
    parser.add_argument(
        "--log-file",
        default="collaborator_update_log.json",
        help="Path to write a JSON execution log.",
    )
    return parser.parse_args()


def get_token() -> str:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Set GH_TOKEN or GITHUB_TOKEN with permission to manage repository collaborators.")
    return token


def list_matching_repos(api: GitHubApi, owner: str, prefix: str, limit: int) -> list[str]:
    repos: list[str] = []
    per_page = min(100, max(1, limit))
    page = 1
    owner_type = None

    owner_lookup = api.request("GET", f"/users/{owner}")
    if owner_lookup.status == 200 and isinstance(owner_lookup.body, dict):
        owner_type = owner_lookup.body.get("type")

    # /users/{owner}/repos is public-only for many cases.
    # Prefer endpoints that include private repositories when token access allows.
    use_org_endpoint = owner_type == "Organization"
    use_authenticated_user_endpoint = owner_type == "User"

    while len(repos) < limit:
        if use_org_endpoint:
            query = urllib.parse.urlencode(
                {
                    "per_page": per_page,
                    "page": page,
                    "type": "all",
                    "sort": "full_name",
                }
            )
            response = api.request("GET", f"/orgs/{owner}/repos?{query}")
        elif use_authenticated_user_endpoint:
            query = urllib.parse.urlencode(
                {
                    "per_page": per_page,
                    "page": page,
                    "affiliation": "owner",
                    "visibility": "all",
                    "sort": "full_name",
                }
            )
            response = api.request("GET", f"/user/repos?{query}")
            if response.status == 200 and isinstance(response.body, list):
                response.body = [
                    repo
                    for repo in response.body
                    if isinstance(repo, dict)
                    and isinstance(repo.get("owner"), dict)
                    and str(repo["owner"].get("login", "")).lower() == owner.lower()
                ]
        else:
            query = urllib.parse.urlencode(
                {
                    "per_page": per_page,
                    "page": page,
                    "type": "all",
                    "sort": "full_name",
                }
            )
            response = api.request("GET", f"/orgs/{owner}/repos?{query}")
            if response.status == 404:
                response = api.request("GET", f"/users/{owner}/repos?{query}")

        if response.status != 200:
            raise RuntimeError(f"Could not list repositories for {owner}: {format_body(response.body)}")

        page_repos = response.body
        if not page_repos:
            break

        for repo in page_repos:
            name = repo.get("name", "")
            if name.startswith(prefix):
                repos.append(name)
                if len(repos) >= limit:
                    break

        if len(page_repos) < per_page:
            break
        page += 1

    return repos


def update_repo(
    api: GitHubApi,
    owner: str,
    repo: str,
    remove_user: str,
    add_user: str,
    permission: str,
    apply_changes: bool,
) -> tuple[bool, dict[str, Any]]:
    full_name = f"{owner}/{repo}"
    print(f"\nRepository: {full_name}")
    details: dict[str, Any] = {
        "repo": repo,
        "full_name": full_name,
        "status": "failed",
        "remove_user": remove_user,
        "add_user": add_user,
        "permission": permission,
    }

    repo_response = api.request("GET", f"/repos/{owner}/{repo}")
    if repo_response.status != 200:
        print(f"  ERROR: cannot access repository ({repo_response.status}): {format_body(repo_response.body)}")
        details["error"] = f"cannot access repository ({repo_response.status}): {format_body(repo_response.body)}"
        return False, details

    if not apply_changes:
        print(f"  DRY RUN: would remove collaborator {remove_user}")
        print(f"  DRY RUN: would add collaborator {add_user} with {permission!r} permission")
        details["status"] = "dry_run"
        return True, details

    remove_response = api.request("DELETE", f"/repos/{owner}/{repo}/collaborators/{remove_user}")
    if remove_response.status == 204:
        print(f"  Removed {remove_user}")
        details["remove_result"] = "removed"
    elif remove_response.status == 404:
        print(f"  {remove_user} was not present or could not be found")
        details["remove_result"] = "not_present_or_not_found"
    else:
        print(f"  ERROR removing {remove_user} ({remove_response.status}): {format_body(remove_response.body)}")
        details["error"] = f"error removing {remove_user} ({remove_response.status}): {format_body(remove_response.body)}"
        return False, details

    add_response = api.request(
        "PUT",
        f"/repos/{owner}/{repo}/collaborators/{add_user}",
        {"permission": permission},
    )
    if add_response.status == 201:
        print(f"  Invited {add_user} with {permission!r} permission")
        details["add_result"] = "invited"
    elif add_response.status == 204:
        print(f"  Added or updated {add_user} with {permission!r} permission")
        details["add_result"] = "added_or_updated"
    else:
        print(f"  ERROR adding {add_user} ({add_response.status}): {format_body(add_response.body)}")
        details["error"] = f"error adding {add_user} ({add_response.status}): {format_body(add_response.body)}"
        return False, details

    details["status"] = "success"
    return True, details


def format_body(body: Any) -> str:
    if isinstance(body, dict):
        return str(body.get("message") or body)
    return str(body)


def write_log(path: str, payload: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, indent=2)
        file_obj.write("\n")


def main() -> int:
    args = parse_args()
    token = get_token()
    api = GitHubApi(token)

    repos = args.repo or list_matching_repos(api, args.owner, args.prefix, args.limit)
    repos = sorted(set(repos))

    if not repos:
        print(f"No repositories found for {args.owner!r} matching prefix {args.prefix!r}.")
        return 1

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"Mode: {mode}")
    print(f"Owner: {args.owner}")
    print(f"Repositories: {', '.join(repos)}")

    successes = 0
    repo_results: list[dict[str, Any]] = []
    for repo in repos:
        ok, details = update_repo(
            api,
            args.owner,
            repo,
            args.remove_user,
            args.add_user,
            args.permission,
            args.apply,
        )
        repo_results.append(details)
        if ok:
            successes += 1

    failures = len(repos) - successes
    print(f"\nDone. Successful: {successes}. Failed: {failures}.")
    log_payload: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if args.apply else "dry_run",
        "owner": args.owner,
        "prefix": args.prefix,
        "remove_user": args.remove_user,
        "add_user": args.add_user,
        "permission": args.permission,
        "repo_count": len(repos),
        "success_count": successes,
        "failure_count": failures,
        "repos": repo_results,
    }
    write_log(args.log_file, log_payload)
    print(f"Log written: {args.log_file}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
