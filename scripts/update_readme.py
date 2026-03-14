#!/usr/bin/env python3
"""
Regenerates the Articles table in README.md between
<!-- ARTICLES_TABLE_START --> and <!-- ARTICLES_TABLE_END --> markers.

Scans articles/ for YYYY-MM-DD-<slug>.md files, reads their H1 title,
and links the corresponding linkedin/ post if it exists.
"""

import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README_PATH = os.path.join(REPO_ROOT, "README.md")
ARTICLES_DIR = os.path.join(REPO_ROOT, "articles")
LINKEDIN_DIR = os.path.join(REPO_ROOT, "linkedin")

PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$")
START_MARKER = "<!-- ARTICLES_TABLE_START -->"
END_MARKER = "<!-- ARTICLES_TABLE_END -->"


def get_h1_title(filepath):
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
    return None


def build_table():
    rows = []
    for filename in sorted(os.listdir(ARTICLES_DIR), reverse=True):
        m = PATTERN.match(filename)
        if not m:
            continue
        date, slug = m.group(1), m.group(2)
        article_path = os.path.join(ARTICLES_DIR, filename)
        title = get_h1_title(article_path) or slug.replace("-", " ").title()
        article_link = f"[{title}](articles/{filename})"

        linkedin_filename = f"{date}-{slug}-linkedin.md"
        linkedin_path = os.path.join(LINKEDIN_DIR, linkedin_filename)
        if os.path.exists(linkedin_path):
            linkedin_link = f"[Post](linkedin/{linkedin_filename})"
        else:
            linkedin_link = "—"

        rows.append(f"| {date} | {article_link} | {linkedin_link} |")

    header = "| Date | Article | LinkedIn |\n|------|---------|----------|"
    return header + "\n" + "\n".join(rows)


def update_readme():
    with open(README_PATH, encoding="utf-8") as f:
        content = f.read()

    table = build_table()
    new_block = f"{START_MARKER}\n{table}\n{END_MARKER}"
    updated = re.sub(
        rf"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}",
        new_block,
        content,
        flags=re.DOTALL,
    )

    if updated == content:
        print("README.md already up to date.")
        return False

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(updated)
    print("README.md updated.")
    return True


if __name__ == "__main__":
    changed = update_readme()
    sys.exit(0 if changed else 0)
