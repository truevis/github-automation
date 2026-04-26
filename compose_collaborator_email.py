#!/usr/bin/env python3
"""Compose collaborator update email from update log JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a markdown email draft from collaborator update log."
    )
    parser.add_argument(
        "--log-file",
        default="collaborator_update_log.json",
        help="Path to JSON log created by update_github_collaborators.py",
    )
    parser.add_argument(
        "--recipient",
        default="BSE-Git",
        help="Recipient name used in greeting.",
    )
    parser.add_argument(
        "--sender",
        default="[Your Name]",
        help="Sender name used in sign-off.",
    )
    parser.add_argument(
        "--output",
        default="email.md",
        help="Output file for markdown email.",
    )
    return parser.parse_args()


def load_log(path: str) -> dict[str, Any]:
    log_path = Path(path)
    if not log_path.exists():
        raise SystemExit(f"Log file not found: {path}")
    with log_path.open("r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)
    if not isinstance(data, dict):
        raise SystemExit("Invalid log file format: expected a JSON object.")
    return data


def build_email(log_data: dict[str, Any], recipient: str, sender: str) -> str:
    owner = str(log_data.get("owner", ""))
    permission = str(log_data.get("permission", "push"))
    add_user = str(log_data.get("add_user", recipient))
    mode = str(log_data.get("mode", "dry_run"))
    repos_raw = log_data.get("repos", [])
    repos: list[dict[str, Any]] = [repo for repo in repos_raw if isinstance(repo, dict)]
    updated_repos = sorted(
        {
            str(repo.get("repo", "")).strip()
            for repo in repos
            if str(repo.get("status", "")) == "success" and str(repo.get("repo", "")).strip()
        }
    )
    dry_run_repos = sorted(
        {
            str(repo.get("repo", "")).strip()
            for repo in repos
            if str(repo.get("status", "")) == "dry_run" and str(repo.get("repo", "")).strip()
        }
    )
    failed_repos = sorted(
        {
            str(repo.get("repo", "")).strip()
            for repo in repos
            if str(repo.get("status", "")) == "failed" and str(repo.get("repo", "")).strip()
        }
    )

    lines: list[str] = []
    lines.append("Subject: GitHub collaborator access has been added")
    lines.append("")
    lines.append(f"Hi {recipient},")
    lines.append("")
    lines.append(f"I've added you as a collaborator to the repositories listed below under the `{owner}` owner.")
    lines.append("")
    lines.append("Permission granted:")
    lines.append("")
    lines.append(f"- `{permission}` access")
    lines.append("- This includes read access (view/clone/pull) and write access (push commits and create branches).")
    lines.append("- This does not include admin-level controls (for example: repository settings, collaborator management, or deletion/transfer actions).")
    lines.append("")
    lines.append("What I completed:")
    lines.append("")
    if mode == "dry_run":
        lines.append("- Performed a dry run only (no collaborator changes applied yet)")
    else:
        lines.append(f"- Added collaborator access for `{add_user}` across repositories listed below")
    lines.append("- Verified the update run targeted the repositories below")
    lines.append("")
    lines.append("Repositories updated:")
    lines.append("")

    display_repos = updated_repos if mode != "dry_run" else dry_run_repos
    if display_repos:
        for repo in display_repos:
            repo_url = f"https://github.com/{owner}/{repo}"
            lines.append(f"- {repo}: [{repo_url}]({repo_url})")
    else:
        lines.append("- None")

    if failed_repos:
        lines.append("")
        lines.append("Repositories that need follow-up:")
        lines.append("")
        for repo in failed_repos:
            repo_url = f"https://github.com/{owner}/{repo}"
            lines.append(f"- {repo}: [{repo_url}]({repo_url})")

    lines.append("")
    lines.append("Please accept any pending GitHub invitations if prompted. Once accepted, you should have read and write access immediately on each repository listed above.")
    lines.append("")
    lines.append("Thanks,")
    lines.append(sender)
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    log_data = load_log(args.log_file)
    email_body = build_email(log_data, args.recipient, args.sender)

    output_path = Path(args.output)
    output_path.write_text(email_body, encoding="utf-8")
    print(f"Email draft written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
