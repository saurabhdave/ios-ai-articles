#!/usr/bin/env python3
"""
scripts/editorial_gate.py
Automated editorial gate for ios-ai-articles.

Checks (run in order so later checks see the already-cleaned state):
  1. No validated code  — codegen path == "omitted"
  2. Banned deprecated Swift APIs in code blocks
  3. Duplicate/near-duplicate article topics (Jaccard > 0.5 on H1 tokens)
  4. Orphaned newsletters  — Big Story title not found in articles/

Removes offending files (article + linkedin + codegen companions; newsletter
.md + .html pairs) and prints a structured summary.

Exit codes:
  0 — gate passed, nothing removed
  1 — gate removed one or more files (caller should commit)

Usage:
  python scripts/editorial_gate.py            # normal run
  python scripts/editorial_gate.py --dry-run  # report only, no deletions
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Paths (relative to repo root, one level above this script)
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES_DIR = os.path.join(REPO_ROOT, "articles")
LINKEDIN_DIR = os.path.join(REPO_ROOT, "linkedin")
CODEGEN_DIR = os.path.join(REPO_ROOT, "codegen")
NEWSLETTER_DIR = os.path.join(REPO_ROOT, "newsletter")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ARTICLE_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$")
NEWSLETTER_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2}-.+)\.(md|html)$")

# Strings that must not appear inside ```swift ... ``` blocks
BANNED_APIS: list[str] = [
    "@Published",
    "@ObservableObject",
    "os_signpost(",
]

JACCARD_THRESHOLD = 0.50

# Common boilerplate words in iOS/Swift article titles that are not
# discriminating for topic identity.  Filtered before Jaccard comparison.
TITLE_STOPWORDS: frozenset[str] = frozenset({
    "migrate", "migrating", "migration",
    "swift", "swiftui", "ios",
    "to", "from", "for", "with", "using", "and", "the", "a", "an", "in",
    "on", "of", "at",
    "patterns", "pattern",
    "apps", "app",
    "production",
})

BIG_STORY_SECTION = "### This Week's Big Story"


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _safe_remove(path: str, removed: list[str], dry_run: bool) -> None:
    """Remove a file if it exists; record the action."""
    if os.path.exists(path):
        rel = os.path.relpath(path, REPO_ROOT)
        if not dry_run:
            os.remove(path)
        removed.append(rel)


def get_h1(filepath: str) -> str | None:
    """Return the first H1 title from a markdown file, or None."""
    try:
        with open(filepath, encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped.startswith("# "):
                    return stripped[2:].strip()
    except OSError:
        pass
    return None


def extract_swift_blocks(content: str) -> list[str]:
    """Return all ```swift ... ``` code block bodies."""
    return re.findall(r"```swift\n(.*?)```", content, re.DOTALL)


def tokenize(title: str) -> set[str]:
    """
    Lowercase word tokens split on non-alphanumeric characters, with common
    iOS/Swift boilerplate words removed so generic terms like 'migrate' or
    'swift' don't create false duplicate matches.
    """
    raw = {t for t in re.split(r"[^a-z0-9]+", title.lower()) if t}
    return raw - TITLE_STOPWORDS


def jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def slug_from_filename(filename: str) -> str | None:
    """'2026-03-14-some-slug.md' → '2026-03-14-some-slug'"""
    m = ARTICLE_PATTERN.match(filename)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def codegen_path(slug: str) -> str:
    return os.path.join(CODEGEN_DIR, f"{slug}-codegen.json")


def linkedin_path(slug: str) -> str:
    return os.path.join(LINKEDIN_DIR, f"{slug}-linkedin.md")


def article_path(slug: str) -> str:
    return os.path.join(ARTICLES_DIR, f"{slug}.md")


def read_codegen_path_field(slug: str) -> str:
    """Return the 'path' field from codegen JSON, or 'missing'."""
    json_path = codegen_path(slug)
    if not os.path.exists(json_path):
        return "missing"
    try:
        with open(json_path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("path", "missing")
    except (OSError, json.JSONDecodeError):
        return "missing"


def remove_article_set(slug: str, removed: list[str], dry_run: bool) -> None:
    """Remove article .md, its linkedin post, and its codegen JSON."""
    _safe_remove(article_path(slug), removed, dry_run)
    _safe_remove(linkedin_path(slug), removed, dry_run)
    _safe_remove(codegen_path(slug), removed, dry_run)


def extract_big_story_title(newsletter_md: str) -> str | None:
    """
    Parse the Big Story title from a newsletter .md file.

    Expected format:
        ### This Week's Big Story

        **<title>**
    """
    try:
        with open(newsletter_md, encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return None

    idx = content.find(BIG_STORY_SECTION)
    if idx == -1:
        return None

    after = content[idx + len(BIG_STORY_SECTION):]
    m = re.search(r"\*\*([^*\n]+)\*\*", after)
    return m.group(1).strip() if m else None


def build_article_h1_set() -> set[str]:
    """Collect all current article H1 titles from articles/."""
    titles: set[str] = set()
    for filename in os.listdir(ARTICLES_DIR):
        if not ARTICLE_PATTERN.match(filename):
            continue
        h1 = get_h1(os.path.join(ARTICLES_DIR, filename))
        if h1:
            titles.add(h1.strip())
    return titles


# ---------------------------------------------------------------------------
# Check 1 — No validated code
# ---------------------------------------------------------------------------

def check_no_validated_code(
    slugs: list[str],
    blocked: dict[str, list[str]],
    removed: list[str],
    dry_run: bool,
) -> None:
    """Block articles whose codegen JSON records path == 'omitted'."""
    for slug in slugs:
        if read_codegen_path_field(slug) == "omitted":
            blocked.setdefault(slug, []).append(
                "codegen path == 'omitted' (no validated Swift code)"
            )
            remove_article_set(slug, removed, dry_run)


# ---------------------------------------------------------------------------
# Check 2 — Banned deprecated APIs
# ---------------------------------------------------------------------------

def check_banned_apis(
    slugs: list[str],
    blocked: dict[str, list[str]],
    removed: list[str],
    dry_run: bool,
) -> None:
    """Block articles that use banned API strings inside swift code blocks."""
    for slug in slugs:
        path = article_path(slug)
        if not os.path.exists(path):
            continue  # already removed by a prior check
        try:
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            continue

        combined = "\n".join(extract_swift_blocks(content))
        hits = [api for api in BANNED_APIS if api in combined]
        if hits:
            blocked.setdefault(slug, []).append(
                f"banned deprecated API(s) in Swift code: {', '.join(hits)}"
            )
            remove_article_set(slug, removed, dry_run)


# ---------------------------------------------------------------------------
# Check 3 — Duplicate / near-duplicate topics
# ---------------------------------------------------------------------------

def check_duplicate_titles(
    slugs: list[str],
    blocked: dict[str, list[str]],
    removed: list[str],
    dry_run: bool,
) -> None:
    """
    Detect article pairs whose H1 titles share Jaccard > JACCARD_THRESHOLD.

    Resolution order (keep the better one):
      1. Keep the article with validated code; remove the one without.
      2. If both have code (or neither), keep the newer file (larger slug
         sorts later because filenames are YYYY-MM-DD-*).
    """
    live = [s for s in slugs if os.path.exists(article_path(s))]

    # Build token sets for live articles
    tokens: dict[str, set[str]] = {}
    h1s: dict[str, str] = {}
    for slug in live:
        h1 = get_h1(article_path(slug))
        if h1:
            h1s[slug] = h1
            tokens[slug] = tokenize(h1)

    processed: set[str] = set()
    for i, slug_a in enumerate(live):
        if slug_a not in tokens or slug_a in processed:
            continue
        for slug_b in live[i + 1:]:
            if slug_b not in tokens or slug_b in processed:
                continue
            score = jaccard(tokens[slug_a], tokens[slug_b])
            if score <= JACCARD_THRESHOLD:
                continue

            # Determine which to keep
            has_code_a = read_codegen_path_field(slug_a) not in ("omitted", "missing")
            has_code_b = read_codegen_path_field(slug_b) not in ("omitted", "missing")

            if has_code_a and not has_code_b:
                loser, winner = slug_b, slug_a
            elif has_code_b and not has_code_a:
                loser, winner = slug_a, slug_b
            else:
                # Both or neither — keep the newer one (lexicographically larger)
                loser = slug_a if slug_a < slug_b else slug_b
                winner = slug_b if loser == slug_a else slug_a

            reason = (
                f"near-duplicate of '{h1s.get(winner, winner)}' "
                f"(Jaccard={score:.2f})"
            )
            blocked.setdefault(loser, []).append(reason)
            remove_article_set(loser, removed, dry_run)
            processed.add(loser)


# ---------------------------------------------------------------------------
# Check 4 — Orphaned newsletters
# ---------------------------------------------------------------------------

def check_orphaned_newsletters(
    blocked_newsletters: dict[str, list[str]],
    removed: list[str],
    dry_run: bool,
) -> None:
    """
    Remove newsletter pairs (.md + .html) where the Big Story title
    does not match any article H1 currently in articles/.
    """
    article_h1s = build_article_h1_set()

    # Group newsletter files by base name (without extension)
    basename_map: dict[str, list[str]] = {}
    for filename in os.listdir(NEWSLETTER_DIR):
        m = NEWSLETTER_PATTERN.match(filename)
        if not m:
            continue
        basename_map.setdefault(m.group(1), []).append(filename)

    for base, files in sorted(basename_map.items()):
        md_file = next((f for f in files if f.endswith(".md")), None)
        if md_file is None:
            continue

        md_path = os.path.join(NEWSLETTER_DIR, md_file)
        big_story = extract_big_story_title(md_path)

        if big_story is None:
            reason = "Big Story title could not be parsed from newsletter"
        elif big_story not in article_h1s:
            reason = f"Big Story '{big_story}' has no matching article H1"
        else:
            continue  # newsletter is valid

        blocked_newsletters.setdefault(base, []).append(reason)
        for f in sorted(files):
            _safe_remove(os.path.join(NEWSLETTER_DIR, f), removed, dry_run)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Editorial gate: validate and clean ios-ai-articles content."
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report violations without deleting any files.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    dry_run: bool = args.dry_run

    if dry_run:
        print("=== Editorial Gate (DRY RUN — no files will be deleted) ===\n")
    else:
        print("=== Editorial Gate ===\n")

    # Collect article slugs sorted ascending (oldest → newest)
    all_slugs: list[str] = sorted(
        filter(None, (slug_from_filename(f) for f in os.listdir(ARTICLES_DIR)))
    )

    blocked: dict[str, list[str]] = {}
    blocked_newsletters: dict[str, list[str]] = {}
    removed: list[str] = []

    # Run checks in dependency order
    check_no_validated_code(all_slugs, blocked, removed, dry_run)
    check_banned_apis(all_slugs, blocked, removed, dry_run)
    check_duplicate_titles(all_slugs, blocked, removed, dry_run)
    check_orphaned_newsletters(blocked_newsletters, removed, dry_run)

    # ---- Summary --------------------------------------------------------
    if not blocked and not blocked_newsletters:
        print("All articles and newsletters passed the editorial gate.")
        return 0

    if blocked:
        print(f"BLOCKED ARTICLES ({len(blocked)}):")
        for slug, reasons in blocked.items():
            print(f"  {slug}")
            for r in reasons:
                print(f"    reason: {r}")

    if blocked_newsletters:
        print(f"\nBLOCKED NEWSLETTERS ({len(blocked_newsletters)}):")
        for base, reasons in blocked_newsletters.items():
            print(f"  {base}")
            for r in reasons:
                print(f"    reason: {r}")

    action = "Would remove" if dry_run else "Removed"
    print(f"\n{action} {len(removed)} file(s):")
    for f in removed:
        print(f"  {f}")

    return 1


if __name__ == "__main__":
    sys.exit(main())
