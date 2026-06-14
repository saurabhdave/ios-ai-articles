#!/usr/bin/env python3
"""
scripts/swift_lint.py
Deterministic, zero-dependency regex guard for Swift code blocks.

WHY THIS EXISTS
---------------
The real check is scripts/swift_typecheck.py (it runs `swiftc`), but that needs
macOS + Xcode. The editorial gate runs on ubuntu, where swiftc is unavailable.
This module encodes the *specific* hallucination/API-misuse classes that have
shipped before as high-precision regexes so the ubuntu gate catches regressions
of them for free.

Two severities:
  ERROR   — never-valid in any Swift program (wrong type name, nonexistent
            member/overload/module, illegal declaration). Safe to block on.
  WARNING — strong smell that is context-dependent or deprecated. Reported only.

Each rule documents the real bug it guards against and the correct form.

USAGE
  python scripts/swift_lint.py                      # lint articles/
  python scripts/swift_lint.py articles/foo.md ...  # specific files
  python scripts/swift_lint.py --warnings           # also print WARNING findings

Exit codes:
  0 — no ERROR findings
  1 — at least one ERROR finding
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES_DIR = os.path.join(REPO_ROOT, "articles")

SWIFT_BLOCK_RE = re.compile(r"```swift\n(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: re.Pattern
    severity: str   # "error" | "warning"
    message: str    # what's wrong + the correct form


# Block-scoped rules (run against each ```swift body).
RULES: list[Rule] = [
    # ---- OSSignposter API misuse (never valid) ---------------------------
    Rule("ossignpost-module",
         re.compile(r"^\s*import\s+OSSignpost\b", re.MULTILINE), "error",
         "no module named 'OSSignpost' — OSSignposter lives in `os` (import os)."),
    Rule("ossignposter-signpostid-type",
         re.compile(r"\bOSSignposter\.SignpostID\b"), "error",
         "the type is `OSSignpostID` (top-level), not `OSSignposter.SignpostID`."),
    Rule("ossignposter-logger-oslog",
         re.compile(r"OSSignposter\(\s*logger:\s*OSLog\("), "error",
         "OSSignposter(logger:) takes a `Logger`, not an `OSLog`; "
         "use OSSignposter(subsystem:category:) or pass a Logger."),
    Rule("endinterval-id-label",
         re.compile(r"\.endInterval\(\s*[^,()]+,\s*id:"), "error",
         "endInterval takes the OSSignpostIntervalState from beginInterval, "
         "not `id:` — capture `let s = beginInterval(...)` then endInterval(name, s)."),
    Rule("endinterval-state-label",
         re.compile(r"\.endInterval\([^)]*\bstate:\s*"), "error",
         "endInterval's state argument is positional, not `state:`."),
    Rule("begininterval-parent",
         re.compile(r"\.beginInterval\([^)]*\bparent:"), "error",
         "OSSignposter.beginInterval has no `parent:` parameter."),
    Rule("ossignposter-emit",
         re.compile(r"\bsignposter\.emit\(|\b\w*[Ss]ignposter\.emit\(\s*\."), "error",
         "OSSignposter has no `emit`; use beginInterval/endInterval/emitEvent."),

    # ---- AppIntents (never valid) ----------------------------------------
    Rule("appintents-validationresult",
         re.compile(r"->\s*ValidationResult\b|\breturn\s+\.valid\b|\.invalid\("), "error",
         "AppIntents has no `ValidationResult`/`validate()` hook; throw an error "
         "conforming to CustomLocalizedStringResourceConvertible instead."),

    # ---- UIKit / SwiftUI trait & color (never valid) ---------------------
    Rule("systemlayoutsize-traitcollection",
         re.compile(r"systemLayoutSizeFitting\([^)]*\btraitCollection:"), "error",
         "systemLayoutSizeFitting has no `traitCollection:` parameter; resolve the "
         "trait-specific font (preferredFont(forTextStyle:compatibleWith:)) or use traitOverrides."),
    Rule("swiftui-color-nscolor-member",
         re.compile(r"\bColor\.(windowBackgroundColor|controlBackgroundColor|"
                    r"textBackgroundColor|underPageBackgroundColor|controlColor)\b"), "error",
         "that is an NSColor member, not SwiftUI Color; use Color(nsColor: .xxx)."),

    # ---- Concurrency / actor declaration (never valid) -------------------
    Rule("mainactor-actor",
         re.compile(r"@MainActor\s+(?:public\s+|final\s+|internal\s+)*actor\b"), "error",
         "`@MainActor actor` is illegal — an actor is already isolated. Use "
         "`@MainActor final class` or a plain `actor`."),
    Rule("task-handle-type",
         re.compile(r"\bTask\.Handle\b"), "error",
         "`Task.Handle` was a beta spelling; the type is just `Task<Success, Failure>`."),

    # ---- RealityKit (never valid) ----------------------------------------
    Rule("entity-destroy",
         re.compile(r"\b(?:Entity|ModelEntity|AnchorEntity)\b[^\n]*\.destroy\(\)"
                    r"|\bmodel\.destroy\(\)|\bentity\.destroy\(\)"), "error",
         "RealityKit's Entity has no `destroy()`; use `removeFromParent()` and drop references."),

    # ---- Deprecated / context-dependent (warn only) ----------------------
    Rule("implementation-only",
         re.compile(r"@_implementationOnly\s+import"), "warning",
         "`@_implementationOnly` is deprecated; prefer Swift 6 `internal import`."),
    Rule("hkworkoutsession-deprecated-init",
         re.compile(r"HKWorkoutSession\(\s*configuration:"), "warning",
         "HKWorkoutSession(configuration:) is deprecated; use "
         "HKWorkoutSession(healthStore:configuration:)."),
    Rule("super-underscore-typo",
         re.compile(r"\bsuper\.\w+\(_[a-z]\w*\)"), "warning",
         "looks like a parameter typo (e.g. super.viewWillDisappear(_animated) "
         "instead of (animated))."),
    Rule("wait-for-in-async",
         re.compile(r"\bwait\(for:\s*\[[^\]]*\],\s*timeout:"), "warning",
         "in an async test use `await fulfillment(of:timeout:)`; wait(for:) is noasync."),
    Rule("dot-handle",
         re.compile(r"\}\s*\.handle\b"), "warning",
         "Task.detached returns a Task directly; there is no `.handle`."),
]

# Article-scoped rules: (predicate on slug+content) -> finding.
WATCHOS_HINT = re.compile(r"watchos|hkworkout|healthkit", re.IGNORECASE)


@dataclass
class Finding:
    slug: str
    rule_id: str
    severity: str
    message: str
    snippet: str


def extract_swift_blocks(content: str) -> list[str]:
    return SWIFT_BLOCK_RE.findall(content)


def blank_comments(s: str) -> str:
    """Replace comment characters with spaces (newlines preserved so line numbers
    stay aligned) while leaving string literals intact. This stops the rules from
    matching API names that appear in explanatory comments or inside URLs."""
    out: list[str] = []
    i, n = 0, len(s)
    in_string = False
    while i < n:
        c = s[i]
        if in_string:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(s[i + 1]); i += 2; continue
            if c == '"':
                in_string = False
            i += 1; continue
        if c == '"':
            in_string = True; out.append(c); i += 1; continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            while i < n and s[i] != "\n":
                out.append(" "); i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "*":
            while i < n and not (s[i] == "*" and i + 1 < n and s[i + 1] == "/"):
                out.append("\n" if s[i] == "\n" else " "); i += 1
            if i < n:
                out.append("  "); i += 2
            continue
        out.append(c); i += 1
    return "".join(out)


def lint_blocks(blocks: list[str], slug: str) -> list[Finding]:
    findings: list[Finding] = []
    for block in blocks:
        code = blank_comments(block)
        original_lines = block.splitlines()
        for rule in RULES:
            m = rule.pattern.search(code)
            if m:
                line = code[:m.start()].count("\n") + 1
                frag = original_lines[line - 1].strip() if line - 1 < len(original_lines) else ""
                findings.append(Finding(slug, rule.id, rule.severity, rule.message, frag[:100]))
    return findings


def lint_article(content: str, slug: str) -> list[Finding]:
    findings = lint_blocks(extract_swift_blocks(content), slug)

    # Article-scoped: MetricKit referenced in a watchOS-topic article (MetricKit
    # is unavailable on watchOS). Warn unless the text already says so.
    if WATCHOS_HINT.search(slug) or WATCHOS_HINT.search(content[:400]):
        if "MetricKit" in content and "not available on watchOS" not in content \
                and "unavailable on watchOS" not in content:
            findings.append(Finding(
                slug, "metrickit-on-watchos", "warning",
                "MetricKit is unavailable on watchOS; use Instruments' Energy Log / "
                "sampled os_log instead.", "MetricKit"))
    return findings


def _slug(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def collect_files(args_files: list[str]) -> list[str]:
    if args_files:
        out: list[str] = []
        for f in args_files:
            af = os.path.abspath(f)
            if os.path.isdir(af):
                out += [os.path.join(af, n) for n in sorted(os.listdir(af)) if n.endswith(".md")]
            else:
                out.append(af)
        return out
    if os.path.isdir(ARTICLES_DIR):
        return [os.path.join(ARTICLES_DIR, n) for n in sorted(os.listdir(ARTICLES_DIR))
                if n.endswith(".md")]
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description="Regex guard for Swift code blocks in articles.")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--warnings", action="store_true", help="Also print WARNING findings.")
    args = ap.parse_args()

    files = collect_files(args.files)
    errors = 0
    warnings = 0
    for path in files:
        try:
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            continue
        for f in lint_article(content, _slug(path)):
            if f.severity == "error":
                errors += 1
                print(f"ERROR  {f.slug} [{f.rule_id}]: {f.message}")
                if f.snippet:
                    print(f"         at: {f.snippet}")
            elif args.warnings:
                warnings += 1
                print(f"warn   {f.slug} [{f.rule_id}]: {f.message}")
                if f.snippet:
                    print(f"         at: {f.snippet}")

    print(f"\nswift_lint: {errors} error(s)" + (f", {warnings} warning(s)" if args.warnings else "")
          + f" across {len(files)} file(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
