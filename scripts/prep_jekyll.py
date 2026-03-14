#!/usr/bin/env python3
"""
Copies articles/YYYY-MM-DD-slug.md → _posts/YYYY-MM-DD-slug.md,
injecting YAML front matter so Jekyll can build them as blog posts.
The original files in articles/ are not modified.
"""

import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES_DIR = os.path.join(REPO_ROOT, "articles")
POSTS_DIR = os.path.join(REPO_ROOT, "_posts")
PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$")

os.makedirs(POSTS_DIR, exist_ok=True)

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
