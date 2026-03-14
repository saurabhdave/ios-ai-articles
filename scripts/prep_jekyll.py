#!/usr/bin/env python3
"""
Copies articles/YYYY-MM-DD-slug.md → _posts/YYYY-MM-DD-slug.md,
and newsletter/YYYY-MM-DD-*.md → _newsletters/YYYY-MM-DD-*.md,
injecting YAML front matter so Jekyll can build them.
The original files are not modified.
"""

import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES_DIR = os.path.join(REPO_ROOT, "articles")
POSTS_DIR = os.path.join(REPO_ROOT, "_posts")
NEWSLETTER_DIR = os.path.join(REPO_ROOT, "newsletter")
NEWSLETTERS_DIR = os.path.join(REPO_ROOT, "_newsletters")
PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$")

os.makedirs(POSTS_DIR, exist_ok=True)
os.makedirs(NEWSLETTERS_DIR, exist_ok=True)

for filename in sorted(os.listdir(ARTICLES_DIR)):
    m = PATTERN.match(filename)
    if not m:
        continue
    date, slug = m.group(1), m.group(2)

    with open(os.path.join(ARTICLES_DIR, filename), encoding="utf-8") as f:
        content = f.read()

    # Already has front matter — copy as-is
    if content.startswith("---"):
        out = content
    else:
        # Extract H1 title; fall back to slug
        title = slug.replace("-", " ").title()
        for line in content.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break

        # Escape quotes in title
        safe_title = title.replace('"', '\\"')

        # Strip the H1 line (Jekyll renders the title from front matter)
        body_lines = content.splitlines(keepends=True)
        body_lines = [
            l for l in body_lines
            if not (l.startswith("# ") and l[2:].strip() == title)
        ]
        body = "".join(body_lines).lstrip("\n")

        front_matter = (
            f'---\n'
            f'layout: post\n'
            f'title: "{safe_title}"\n'
            f'date: {date}\n'
            f'categories: ios swift\n'
            f'---\n\n'
        )
        out = front_matter + body

    out_path = os.path.join(POSTS_DIR, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"Prepared: {filename}")

if os.path.isdir(NEWSLETTER_DIR):
    for filename in sorted(os.listdir(NEWSLETTER_DIR)):
        m = PATTERN.match(filename)
        if not m:
            continue
        date, slug = m.group(1), m.group(2)

        with open(os.path.join(NEWSLETTER_DIR, filename), encoding="utf-8") as f:
            content = f.read()

        # Already has front matter — copy as-is
        if content.startswith("---"):
            out = content
        else:
            # Extract title from first ## heading (newsletters use H2 as doc title)
            title = slug.replace("-", " ").title()
            for line in content.splitlines():
                if line.startswith("## "):
                    title = line[3:].strip()
                    break

            safe_title = title.replace('"', '\\"')

            # Strip the ## title line from body
            body_lines = content.splitlines(keepends=True)
            body_lines = [
                l for l in body_lines
                if not (l.startswith("## ") and l[3:].strip() == title)
            ]
            body = "".join(body_lines).lstrip("\n")

            front_matter = (
                f'---\n'
                f'layout: newsletter\n'
                f'title: "{safe_title}"\n'
                f'date: {date}\n'
                f'categories: newsletter\n'
                f'---\n\n'
            )
            out = front_matter + body

        out_path = os.path.join(NEWSLETTERS_DIR, filename)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"Prepared newsletter: {filename}")
