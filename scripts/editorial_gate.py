#!/usr/bin/env python3
"""
scripts/editorial_gate.py
Automated editorial gate for ios-ai-articles.

Checks (run in order so later checks see the already-cleaned state):
  1. No validated code  — codegen path == "omitted"
  2. Banned deprecated Swift APIs in code blocks
  3. Malformed article titles — missing/truncated/dangling H1s
  4. Duplicate/near-duplicate article topics (Jaccard > 0.5 on H1 tokens)
  5. Orphaned newsletters  — Big Story title not found in articles/

Removes offending files (article + linkedin + codegen companions; newsletter
.md + .html pairs) and prints a structured summary.

Advisory check (warnings only, no deletions):
  6. Code logic review — OpenAI-powered review of Swift code blocks for issues
     that swiftc cannot catch (data races, wrong @Bindable usage, etc.).
     Requires OPENAI_API_KEY env var.  Controlled by CODE_REVIEW_ENABLED
     (default "true").  Findings written to outputs/code_review_log.json.

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
import subprocess
import sys

# Same-directory module: high-precision regex guard for Swift code blocks.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from swift_lint import lint_article as _swift_lint_article
except ImportError:  # pragma: no cover - guard if the module is missing
    _swift_lint_article = None

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
LINKEDIN_ARTIFACT_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)-linkedin\.md$")
CODEGEN_ARTIFACT_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)-codegen\.json$")

TITLE_MIN_ALPHA_TOKENS = 3
TRAILING_TITLE_CONNECTORS: frozenset[str] = frozenset({
    "and", "or", "for", "with", "to", "from", "in", "on", "of",
})

# Strings that must not appear inside ```swift ... ``` blocks
BANNED_APIS: list[str] = [
    "@Published",
    "@ObservableObject",
    "os_signpost(",
]

JACCARD_THRESHOLD = 0.50

# Common boilerplate words in iOS/Swift article titles that are not
# discriminating for topic identity. Filtered before Jaccard comparison.
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

OUTPUTS_DIR = os.path.join(REPO_ROOT, "outputs")
CODE_REVIEW_LOG = os.path.join(OUTPUTS_DIR, "code_review_log.json")

CODE_REVIEW_SYSTEM_PROMPT = """\
You are a Swift 6 code reviewer. Review the following Swift code block from a technical article.

Check for:
1. Data races — mutable state accessed from multiple actors/tasks without isolation
2. Wrong @Bindable usage — @Bindable must wrap a reference passed in from outside, never a locally-owned @Observable
3. Misleading patterns — code that compiles but teaches incorrect idioms (e.g. Task.detached from UI code without justification)
4. Missing actor isolation — classes with mutable dictionaries/arrays used in async context without @MainActor or actor keyword
5. Wrong API usage — any Swift 6 API used incorrectly

Respond ONLY in this JSON format:
{
  "has_issues": true/false,
  "issues": [
    {"severity": "error|warning", "description": "specific issue", "line_hint": "code fragment where issue occurs"}
  ]
}

If no issues found: {"has_issues": false, "issues": []}
"""


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


# Stopwords for normalise_title — grammatical filler that inflates topic distance.
_NORMALISE_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "for", "in", "on", "of", "to", "with",
    "using", "via", "how", "what", "your", "my", "our", "their",
    "is", "are", "was", "were", "be", "been", "being", "have", "has",
})


def normalise_title(title: str) -> set[str]:
    """Lowercase, remove stopwords, stem verb forms (profiling→profil), return a set.

    Strips trailing 'ing' from tokens longer than 6 characters so that
    'profiling' and 'profile' produce overlapping stems, catching near-duplicates
    that differ only in gerund vs. base-verb phrasing.
    """
    tokens = re.findall(r"\w+", title.lower())
    tokens = [t for t in tokens if t not in _NORMALISE_STOPWORDS and t not in TITLE_STOPWORDS]
    normalised: list[str] = []
    for t in tokens:
        if t.endswith("ing") and len(t) > 6:
            normalised.append(t[:-3])  # "profiling" → "profil", "rendering" → "render"
        else:
            normalised.append(t)
    return set(normalised)


def jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def slug_from_filename(filename: str) -> str | None:
    """'2026-03-14-some-slug.md' → '2026-03-14-some-slug'"""
    m = ARTICLE_PATTERN.match(filename)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def _git_changed_paths() -> set[str]:
    """Return changed repo-relative paths from the push event diff, if available."""
    before = os.getenv("GATE_DIFF_BEFORE", "").strip()
    after = os.getenv("GATE_DIFF_AFTER", "").strip()
    if not before or not after or re.fullmatch(r"0+", before):
        return set()
    try:
        output = subprocess.check_output(
            ["git", "diff", "--name-only", f"{before}..{after}"],
            cwd=REPO_ROOT,
            text=True,
        )
    except Exception:
        return set()
    return {line.strip() for line in output.splitlines() if line.strip()}


def slug_from_changed_path(path: str) -> str | None:
    """Map changed article/linkedin/codegen paths to the canonical article slug."""
    filename = os.path.basename(path)
    if path.startswith("articles/"):
        return slug_from_filename(filename)

    if path.startswith("linkedin/"):
        match = LINKEDIN_ARTIFACT_PATTERN.match(filename)
        if match:
            return f"{match.group(1)}-{match.group(2)}"

    if path.startswith("codegen/"):
        match = CODEGEN_ARTIFACT_PATTERN.match(filename)
        if match:
            return f"{match.group(1)}-{match.group(2)}"

    return None


def newsletter_base_from_path(path: str) -> str | None:
    """Return newsletter basename without extension for a changed newsletter artifact."""
    if not path.startswith("newsletter/"):
        return None
    match = NEWSLETTER_PATTERN.match(os.path.basename(path))
    return match.group(1) if match else None


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


def title_sanity_reason(title: str | None) -> str | None:
    """Return a concrete reason when an article H1 is clearly malformed."""
    if title is None:
        return "missing H1 title"

    stripped = title.strip()
    if not stripped:
        return "empty H1 title"
    if stripped[-1] in {"/", ":", "-"}:
        return f"title ends with dangling punctuation ({stripped[-1]!r})"

    words = re.findall(r"[A-Za-z]+", stripped)
    if len(words) < TITLE_MIN_ALPHA_TOKENS:
        return f"title has fewer than {TITLE_MIN_ALPHA_TOKENS} alphabetic tokens"

    if words[-1].lower() in TRAILING_TITLE_CONNECTORS:
        return f"title ends with dangling connector ({words[-1]!r})"

    return None


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
# Check 2b — Hallucinated / misused Swift APIs (deterministic regex guard)
# ---------------------------------------------------------------------------

def check_swift_api_misuse(
    slugs: list[str],
    blocked: dict[str, list[str]],
    removed: list[str],
    dry_run: bool,
) -> None:
    """Block articles whose Swift blocks contain never-valid API patterns
    (wrong OSSignposter overloads, `@MainActor actor`, invented AppIntents
    `ValidationResult`, `Task.Handle`, RealityKit `Entity.destroy()`, …).

    ERROR-severity findings remove the article; WARNING findings are advisory and
    only printed. This is the ubuntu-CI counterpart to scripts/swift_typecheck.py
    (which needs Xcode and runs on macOS).
    """
    if _swift_lint_article is None:
        print("[SWIFT-LINT] swift_lint module unavailable — skipping API-misuse check")
        return

    for slug in slugs:
        path = article_path(slug)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            continue

        findings = _swift_lint_article(content, slug)
        errors = [f for f in findings if f.severity == "error"]
        warnings = [f for f in findings if f.severity == "warning"]

        for w in warnings:
            print(f"[SWIFT-LINT] {slug}: warning [{w.rule_id}] {w.message}")

        if errors:
            reasons = "; ".join(f"{e.rule_id}: {e.message}" for e in errors)
            blocked.setdefault(slug, []).append(f"swift API misuse — {reasons}")
            remove_article_set(slug, removed, dry_run)


# ---------------------------------------------------------------------------
# Check 3 — Malformed/truncated article titles
# ---------------------------------------------------------------------------

def check_title_sanity(
    slugs: list[str],
    blocked: dict[str, list[str]],
    removed: list[str],
    dry_run: bool,
) -> None:
    """Block changed articles whose H1 title is clearly malformed."""
    for slug in slugs:
        path = article_path(slug)
        if not os.path.exists(path):
            continue
        reason = title_sanity_reason(get_h1(path))
        if reason is None:
            continue
        blocked.setdefault(slug, []).append(reason)
        remove_article_set(slug, removed, dry_run)


# ---------------------------------------------------------------------------
# Check 4 — Duplicate / near-duplicate topics
# ---------------------------------------------------------------------------

def check_duplicate_titles(
    changed_slugs: list[str],
    all_slugs: list[str],
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
    live = [s for s in all_slugs if os.path.exists(article_path(s))]
    changed_live = [s for s in changed_slugs if os.path.exists(article_path(s))]
    changed_set = set(changed_live)

    tokens: dict[str, set[str]] = {}
    h1s: dict[str, str] = {}
    for slug in live:
        h1 = get_h1(article_path(slug))
        if h1:
            h1s[slug] = h1
            tokens[slug] = normalise_title(h1)

    processed: set[str] = set()
    for slug_a in changed_live:
        if slug_a not in tokens or slug_a in processed:
            continue
        for slug_b in live:
            if slug_b == slug_a:
                continue
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
                loser = slug_a if slug_a < slug_b else slug_b
                winner = slug_b if loser == slug_a else slug_a

            if loser not in changed_set:
                continue

            reason = (
                f"near-duplicate of '{h1s.get(winner, winner)}' "
                f"(Jaccard={score:.2f})"
            )
            blocked.setdefault(loser, []).append(reason)
            remove_article_set(loser, removed, dry_run)
            processed.add(loser)


# ---------------------------------------------------------------------------
# Check 5 — Orphaned newsletters
# ---------------------------------------------------------------------------

def check_orphaned_newsletters(
    changed_bases: list[str],
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

    target_bases = sorted(changed_bases) if changed_bases else sorted(basename_map)

    for base in target_bases:
        files = basename_map.get(base, [])
        if not files:
            continue
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
# Check 6 — Code logic review (advisory, OpenAI-powered)
# ---------------------------------------------------------------------------

def review_code_logic(slugs: list[str], openai_client) -> None:
    """
    For each live article, extract Swift code blocks and send them to the
    OpenAI API for logic review.  Findings are warnings only — no files are
    removed.  All findings are written to outputs/code_review_log.json.

    Args:
        slugs:         List of article slugs to review (same format used
                       throughout the gate).
        openai_client: An initialised openai.OpenAI client instance.
    """
    os.makedirs(OUTPUTS_DIR, exist_ok=True)

    # slug → list of issue dicts reported by the model
    all_findings: dict[str, list[dict]] = {}
    # slugs that have at least one "error"-severity issue
    code_warnings: list[str] = []

    for slug in slugs:
        path = article_path(slug)
        if not os.path.exists(path):
            continue

        try:
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            continue

        blocks = extract_swift_blocks(content)
        if not blocks:
            continue

        slug_findings: list[dict] = []

        for block in blocks:
            try:
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": CODE_REVIEW_SYSTEM_PROMPT},
                        {"role": "user", "content": block},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0,
                )
                raw = response.choices[0].message.content.strip()
                result = json.loads(raw)
            except Exception as exc:
                print(f"[CODE-REVIEW] {slug}: API error — {exc}")
                continue

            if not result.get("has_issues"):
                continue

            for issue in result.get("issues", []):
                severity = issue.get("severity", "warning")
                desc = issue.get("description", "unknown issue")
                hint = issue.get("line_hint", "")
                hint_part = f" | near: {hint}" if hint else ""
                print(f"[CODE-REVIEW] {slug}: {desc}{hint_part}")
                slug_findings.append(issue)
                if severity == "error" and slug not in code_warnings:
                    code_warnings.append(slug)

        if slug_findings:
            all_findings[slug] = slug_findings

    with open(CODE_REVIEW_LOG, "w", encoding="utf-8") as fh:
        json.dump(all_findings, fh, indent=2)

    if code_warnings:
        print(
            f"\n[CODE-REVIEW] {len(code_warnings)} article(s) flagged with errors: "
            + ", ".join(code_warnings)
        )
    elif all_findings:
        print(
            f"\n[CODE-REVIEW] {len(all_findings)} article(s) have warnings. "
            f"See outputs/code_review_log.json"
        )
    else:
        print("[CODE-REVIEW] No code logic issues found.")


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

    all_slugs: list[str] = sorted(
        filter(None, (slug_from_filename(f) for f in os.listdir(ARTICLES_DIR)))
    )
    changed_paths = _git_changed_paths()
    changed_slugs = sorted(
        filter(None, {slug_from_changed_path(path) for path in changed_paths})
    )
    changed_newsletter_bases = sorted(
        filter(None, {newsletter_base_from_path(path) for path in changed_paths})
    )

    review_slugs = changed_slugs or all_slugs
    newsletter_bases = changed_newsletter_bases

    blocked: dict[str, list[str]] = {}
    blocked_newsletters: dict[str, list[str]] = {}
    removed: list[str] = []

    # Run checks in dependency order
    check_no_validated_code(review_slugs, blocked, removed, dry_run)
    check_banned_apis(review_slugs, blocked, removed, dry_run)
    check_swift_api_misuse(review_slugs, blocked, removed, dry_run)
    check_title_sanity(review_slugs, blocked, removed, dry_run)
    check_duplicate_titles(review_slugs, all_slugs, blocked, removed, dry_run)
    check_orphaned_newsletters(newsletter_bases, blocked_newsletters, removed, dry_run)

    # ---- Advisory: code logic review (OpenAI-powered) -------------------
    if os.getenv("OPENAI_API_KEY") and os.getenv("CODE_REVIEW_ENABLED", "true") == "true":
        try:
            import openai as _openai  # optional dependency
            openai_client = _openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            review_code_logic(review_slugs, openai_client)
        except ImportError:
            print("[CODE-REVIEW] openai package not installed — skipping code logic review")

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
