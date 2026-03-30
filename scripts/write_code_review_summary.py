#!/usr/bin/env python3
"""
scripts/write_code_review_summary.py
Reads outputs/code_review_log.json and appends a formatted markdown table
to $GITHUB_STEP_SUMMARY.  No-ops silently when the log file does not exist
or GITHUB_STEP_SUMMARY is not set (e.g. local runs).
"""

from __future__ import annotations

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(REPO_ROOT, "outputs", "code_review_log.json")


def main() -> None:
    if not os.path.exists(LOG_PATH):
        return

    try:
        with open(LOG_PATH, encoding="utf-8") as fh:
            data: dict[str, list[dict]] = json.load(fh)
    except Exception as exc:
        print(f"write_code_review_summary: could not read log — {exc}", file=sys.stderr)
        return

    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return

    with open(summary_file, "a", encoding="utf-8") as out:
        out.write("## Code Review Findings\n\n")
        if not data:
            out.write("No code logic issues found.\n")
            return

        out.write(f"**{len(data)} article(s) with issues:**\n\n")
        out.write("| Article | Severity | Description | Line Hint |\n")
        out.write("|---------|----------|-------------|----------|\n")
        for slug, issues in sorted(data.items()):
            for issue in issues:
                severity = issue.get("severity", "")
                desc = issue.get("description", "").replace("|", "\\|")
                hint = issue.get("line_hint", "").replace("|", "\\|")
                hint_cell = f"`{hint}`" if hint else ""
                out.write(f"| {slug} | {severity} | {desc} | {hint_cell} |\n")


if __name__ == "__main__":
    main()
