#!/usr/bin/env python3
"""
scripts/swift_typecheck.py
Real `swiftc -typecheck` gate for the Swift code blocks in articles/.

WHY THIS EXISTS
---------------
The codegen pipeline only validated the single canonical "Swift/SwiftUI Code
Example" per article; the inline section snippets shipped unchecked, which is
where the API-misuse bugs lived (wrong OSSignposter overloads, invented
RealityKit/AppIntents members, reversed withTaskCancellationHandler, etc.).
This tool compiles EVERY ```swift block against the real SDK.

It requires Xcode (`xcrun`, `swiftc`), so it runs on macOS — locally before
publishing, or in an opt-in macOS CI job. The ubuntu editorial gate gets a
zero-dependency regex guard instead (see scripts/swift_lint.py).

STUB TOLERANCE
--------------
Article snippets reference undefined helper symbols on purpose (ProjectAPI,
RemoteConfig, Model, …). A naive typecheck would fail on all of them. So we
treat "cannot find … in scope" / "unresolved identifier" as EXPECTED (a stub),
record those identifier names, and then drop any cascading diagnostic that
mentions a stub identifier. What remains are real API errors: wrong argument
labels, missing/extra arguments, no-such-member on real SDK types, protocol
conformance failures, actor-isolation violations, etc.

SDK SELECTION
-------------
Per article we pick the SDK from the frontmatter topic / filename / code
imports: HealthKit→watchOS, AppKit/NSView/NSAccessibility→macOS, everything
else→iOS simulator. PackagePlugin blocks are compiled against the toolchain's
PluginAPI module.

USAGE
-----
  python scripts/swift_typecheck.py                 # all of articles/ and _posts/
  python scripts/swift_typecheck.py articles/foo.md # specific files
  python scripts/swift_typecheck.py --verbose       # show kept + dropped diagnostics

Exit codes:
  0 — every block either compiled or failed only on stub references
  1 — at least one block has a real compile error
  2 — environment problem (no xcrun / SDK), nothing checked
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES_DIR = os.path.join(REPO_ROOT, "articles")
POSTS_DIR = os.path.join(REPO_ROOT, "_posts")

SWIFT_BLOCK_RE = re.compile(r"```swift\n(.*?)```", re.DOTALL)

# Diagnostics that mean "you referenced something we never defined" — expected
# for illustrative snippets, so they do not count as failures.
STUB_DIAG_RE = re.compile(
    r"cannot find (?:type |protocol )?'([^']+)' in scope"
    r"|use of unresolved identifier '([^']+)'"
    r"|cannot find '([^']+)' in scope"
)
# A diagnostic line that points at a real error worth failing on.
ERROR_LINE_RE = re.compile(r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+): error: (?P<msg>.*)$")

# Concurrency / actor-isolation diagnostics are mode-sensitive (Swift 5 vs 6) and
# pedantic — they are NOT the hallucination class this gate targets. We surface
# them but only fail the build on them under --strict-concurrency.
# Note: deliberately does NOT match structural declaration errors like
# "actor 'X' cannot have a global actor" (the @MainActor-on-actor mistake) — those
# are hard bugs, so "global actor" is excluded here.
CONCURRENCY_DIAG_RE = re.compile(
    r"#ActorIsolatedCall|#MutableGlobalVariable|#SendableClosureCaptures"
    r"|actor-isolated|concurrency-safe|nonisolated"
    r"|is not concurrent|non-Sendable|: 'Sendable'|isolated conformance",
    re.IGNORECASE,
)


@dataclass
class SDKTarget:
    sdk: str          # xcrun --sdk value
    triple: str       # -target triple
    extra: list[str] = field(default_factory=list)
    preamble: list[str] = field(default_factory=list)  # modules to import-inject


# Framework → regex of symbols that signal the block needs it. We inject an
# import ONLY when its signals appear, so we don't pull in conflicting modules
# (e.g. importing RealityKit would make SwiftUI's `Scene` ambiguous). Always-safe
# base modules (Foundation/Combine/os…) are injected unconditionally.
_BASE_IMPORTS = ["Foundation", "Combine", "OSLog", "os", "Observation", "CoreGraphics"]
_FRAMEWORK_SIGNALS: list[tuple[str, re.Pattern]] = [
    ("SwiftUI", re.compile(r"\b(View|Text|VStack|HStack|ZStack|some View|@State|@Environment|"
                           r"EnvironmentKey|EnvironmentValues|ViewModifier|Layout|Scene|App|"
                           r"NavigationStack|ContentSizeCategory|ProposedViewSize)\b")),
    ("UIKit", re.compile(r"\bUI[A-Z]\w+")),
    ("AppKit", re.compile(r"\bNS(View|Accessibility|Color|App|Window|ViewController|Image|"
                          r"ViewRepresentable)\w*")),
    ("RealityKit", re.compile(r"\b(RealityKit|ModelEntity|AnchorEntity|MeshResource|ARView)\b"
                              r"|\bEntity\b")),
    ("AppIntents", re.compile(r"\b(AppIntent|IntentResult|AppEnum|ParameterSummary|"
                              r"LocalizedStringResource|ReturnsValue|@Parameter)\b")),
    ("WidgetKit", re.compile(r"\b(WidgetCenter|TimelineProvider|TimelineEntry|Widget)\b")),
    ("HealthKit", re.compile(r"\bHK[A-Z]\w+")),
    ("CryptoKit", re.compile(r"\b(CryptoKit|SHA256|SHA512|HMAC|SymmetricKey)\b")),
]


def _platform_fw_dir(sdk: str) -> str | None:
    """Developer framework dir that holds XCTest for a given simulator/SDK."""
    plat = {
        "iphonesimulator": "iPhoneSimulator",
        "watchsimulator": "WatchSimulator",
        "macosx": "MacOSX",
    }.get(sdk)
    if not plat:
        return None
    try:
        dev = subprocess.check_output(["xcode-select", "-p"], text=True).strip()
    except Exception:
        return None
    cand = os.path.join(dev, "Platforms", f"{plat}.platform",
                        "Developer", "Library", "Frameworks")
    return cand if os.path.isdir(cand) else None


# Which injected frameworks are available on each SDK (so we never inject a
# module that triggers a "no such module" false failure).
_SDK_AVAILABLE = {
    "iphonesimulator": {"SwiftUI", "UIKit", "RealityKit", "AppIntents", "WidgetKit", "CryptoKit"},
    "macosx": {"SwiftUI", "AppKit", "RealityKit", "AppIntents", "WidgetKit", "CryptoKit"},
    "watchsimulator": {"SwiftUI", "AppIntents", "WidgetKit", "CryptoKit", "HealthKit"},
}


def _signaled_frameworks(block: str) -> set[str]:
    return {name for name, rx in _FRAMEWORK_SIGNALS if rx.search(block)}


def detect_target(article_text: str, block: str) -> SDKTarget:
    """Pick the SDK/target for a block from its own imports/symbols first."""
    # PackagePlugin blocks are host tools — plugin module, no UI preamble.
    if re.search(r"\bimport PackagePlugin\b", block):
        ppdir = _plugin_api_dir()
        extra = ["-parse-as-library"]
        if ppdir:
            extra += ["-I", ppdir]
        return SDKTarget("macosx", "arm64-apple-macos14.0", extra, preamble=["Foundation"])

    signals = _signaled_frameworks(block)

    if "HealthKit" in signals:
        sdk, triple = "watchsimulator", "arm64-apple-watchos11.0-simulator"
    elif "AppKit" in signals:
        sdk, triple = "macosx", "arm64-apple-macos14.0"
    elif "UIKit" in signals:
        sdk, triple = "iphonesimulator", "arm64-apple-ios18.0-simulator"
    else:
        sdk, triple = "iphonesimulator", "arm64-apple-ios18.0-simulator"

    return _with_preamble(SDKTarget(sdk, triple), block, signals)


def _existing_imports(block: str) -> set[str]:
    """Modules the block already imports (any access level / @_implementationOnly)."""
    return set(re.findall(
        r"^\s*(?:@_implementationOnly\s+|public\s+|internal\s+|fileprivate\s+|private\s+)?"
        r"import\s+(\w+)",
        block, re.MULTILINE,
    ))


def _with_preamble(t: SDKTarget, block: str, signals: set[str]) -> SDKTarget:
    """Inject base modules + signaled frameworks available on this SDK, skipping
    anything the block already imports (so we never double-import or clash on the
    block's chosen access level, e.g. `internal import CryptoKit`)."""
    already = _existing_imports(block)
    injected = [m for m in _BASE_IMPORTS if m not in already]
    for fw in ("SwiftUI", "UIKit", "AppKit", "RealityKit", "AppIntents", "WidgetKit",
               "HealthKit", "CryptoKit"):
        if fw in signals and fw in _SDK_AVAILABLE.get(t.sdk, set()) and fw not in already:
            injected.append(fw)
    t.preamble = list(dict.fromkeys(injected))

    # A block declaring @main is a whole program entry point.
    if re.search(r"^\s*@main\b", block, re.MULTILINE):
        t.extra.append("-parse-as-library")

    if "xctest" in block.lower():
        fw = _platform_fw_dir(t.sdk)
        if fw:
            t.extra += ["-F", fw, "-I", fw]
        if "XCTest" not in already:
            t.preamble.append("XCTest")
    return t


# Appended to every swiftc invocation; set from CLI (--swift6 adds strict mode).
GLOBAL_EXTRA: list[str] = []


def _xcrun_ok() -> bool:
    try:
        subprocess.run(["xcrun", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


_SDK_PATH_CACHE: dict[str, str | None] = {}


def _sdk_path(sdk: str) -> str | None:
    if sdk not in _SDK_PATH_CACHE:
        try:
            out = subprocess.check_output(
                ["xcrun", "--sdk", sdk, "--show-sdk-path"], text=True
            ).strip()
            _SDK_PATH_CACHE[sdk] = out or None
        except Exception:
            _SDK_PATH_CACHE[sdk] = None
    return _SDK_PATH_CACHE[sdk]


_PLUGIN_DIR_CACHE: list[str | None] = []


def _plugin_api_dir() -> str | None:
    if _PLUGIN_DIR_CACHE:
        return _PLUGIN_DIR_CACHE[0]
    found = None
    try:
        dev = subprocess.check_output(["xcode-select", "-p"], text=True).strip()
        cand = os.path.join(
            dev, "Toolchains", "XcodeDefault.xctoolchain",
            "usr", "lib", "swift", "pm", "PluginAPI",
        )
        if os.path.isdir(cand):
            found = cand
    except Exception:
        found = None
    _PLUGIN_DIR_CACHE.append(found)
    return found


def extract_blocks(text: str) -> list[str]:
    return [b for b in SWIFT_BLOCK_RE.findall(text)]


# In-block marker for code that is explicitly pseudocode (references symbols that
# do not and will not exist). Anti-pattern "before" examples are NOT skipped —
# they should still compile (the point is bad practice, not invalid syntax), so a
# real type error in them is worth catching.
_SKIP_MARKER_RE = re.compile(r"\bpseudo(?:code)?\b", re.IGNORECASE)


def is_illustrative_fragment(block: str) -> bool:
    return bool(_SKIP_MARKER_RE.search(block))


def typecheck_block(block: str, target: SDKTarget) -> tuple[list[str], list[str], list[str]]:
    """
    Typecheck one block. Returns (hard_errors, concurrency_errors, dropped_stubs).

    hard_errors:        wrong member/label/module/type/conformance — the
                        hallucination class; these fail the gate.
    concurrency_errors: mode-sensitive actor-isolation diagnostics; reported but
                        only fail under --strict-concurrency.
    dropped_stubs:      diagnostics dropped because they reference a stub symbol.
    """
    sdk_path = _sdk_path(target.sdk)
    if sdk_path is None:
        return ([f"(SDK '{target.sdk}' unavailable)"], [], [])

    # Inject an SDK-appropriate import preamble so import-less fragments resolve
    # their framework types; real API-misuse errors still surface.
    preamble = "".join(f"import {m}\n" for m in target.preamble)
    source = preamble + "\n" + block

    with tempfile.NamedTemporaryFile(
        "w", suffix=".swift", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(source)
        tmp = fh.name

    try:
        cmd = [
            "xcrun", "--sdk", target.sdk, "swiftc", "-typecheck",
            "-sdk", sdk_path, "-target", target.triple,
            *target.extra, *GLOBAL_EXTRA, tmp,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        diags = proc.stderr.splitlines()
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass

    # First pass: collect stub identifier names.
    stub_names: set[str] = set()
    for line in diags:
        m = STUB_DIAG_RE.search(line)
        if m:
            stub_names.update(n for n in m.groups() if n)

    hard: list[str] = []
    concurrency: list[str] = []
    dropped: list[str] = []
    for line in diags:
        em = ERROR_LINE_RE.match(line.strip())
        if not em:
            continue
        msg = em.group("msg")
        # Drop the stub-declaration errors themselves.
        if STUB_DIAG_RE.search(line):
            dropped.append(line.strip())
            continue
        # Drop cascades that reference a stub identifier.
        if any(re.search(rf"'{re.escape(n)}'", msg) for n in stub_names):
            dropped.append(line.strip())
            continue
        if CONCURRENCY_DIAG_RE.search(msg):
            concurrency.append(line.strip())
        else:
            hard.append(line.strip())

    return hard, concurrency, dropped


def _git_changed_md(base: str, head: str) -> list[str] | None:
    """Changed articles/ .md files in base..head, or None if a diff is unavailable."""
    if not head or not base or re.fullmatch(r"0+", base):
        return None
    try:
        out = subprocess.check_output(
            ["git", "-C", REPO_ROOT, "diff", "--name-only", f"{base}..{head}"],
            text=True, stderr=subprocess.DEVNULL,
        )
    except Exception:
        return None
    files = [
        os.path.join(REPO_ROOT, p) for p in out.splitlines()
        if p.startswith("articles/") and p.endswith(".md")
    ]
    return [f for f in files if os.path.exists(f)]


def changed_files() -> list[str] | None:
    """Resolve changed articles from the push diff (GATE_DIFF_*) or the last commit.

    Returns a list (possibly empty when nothing changed) or None when no diff
    could be resolved (caller should fall back to checking everything).
    """
    base = os.getenv("GATE_DIFF_BEFORE", "").strip()
    head = os.getenv("GATE_DIFF_AFTER", "").strip() or "HEAD"
    result = _git_changed_md(base, head)
    if result is None:
        result = _git_changed_md("HEAD~1", "HEAD")
    return result


def collect_files(args_files: list[str]) -> list[str]:
    if args_files:
        out: list[str] = []
        for f in args_files:
            af = os.path.abspath(f)
            if os.path.isdir(af):
                out += [os.path.join(af, n) for n in sorted(os.listdir(af))
                        if n.endswith(".md")]
            else:
                out.append(af)
        return out
    files: list[str] = []
    for d in (ARTICLES_DIR, POSTS_DIR):
        if os.path.isdir(d):
            for name in sorted(os.listdir(d)):
                if name.endswith(".md"):
                    files.append(os.path.join(d, name))
    # Prefer articles/ when both exist (identical bodies); de-dupe by basename.
    seen: dict[str, str] = {}
    for f in files:
        seen.setdefault(os.path.basename(f), f)
    return list(seen.values())


def main() -> int:
    ap = argparse.ArgumentParser(description="Typecheck Swift code blocks in articles.")
    ap.add_argument("files", nargs="*", help="Specific markdown files (default: articles/ + _posts/)")
    ap.add_argument("--verbose", action="store_true", help="Show kept and dropped diagnostics")
    ap.add_argument("--swift6", action="store_true",
                    help="Typecheck in Swift 6 language mode (matches codegen's stated mode; "
                         "surfaces strict actor-isolation errors).")
    ap.add_argument("--strict-concurrency", action="store_true",
                    help="Also fail on actor-isolation / global-mutable-state diagnostics "
                         "(off by default since they are mode-sensitive, not the hallucination "
                         "class this gate targets).")
    ap.add_argument("--changed", action="store_true",
                    help="Only check articles changed in the push diff (GATE_DIFF_BEFORE/AFTER) "
                         "or the last commit; falls back to all when no diff is resolvable.")
    args = ap.parse_args()

    if args.swift6:
        GLOBAL_EXTRA.extend(["-swift-version", "6"])

    if not _xcrun_ok():
        print("swift_typecheck: xcrun/swiftc not available (needs macOS + Xcode); skipping.")
        return 2

    if args.changed and not args.files:
        changed = changed_files()
        if changed is None:
            print("swift_typecheck: --changed could not resolve a diff; checking all.")
            files = collect_files([])
        elif not changed:
            print("swift_typecheck: no changed articles to check.")
            return 0
        else:
            files = changed
    else:
        files = collect_files(args.files)
    if not files:
        print("swift_typecheck: no markdown files found.")
        return 2

    total_blocks = 0
    skipped = 0
    failing = 0
    concurrency_only = 0
    fail_details: list[tuple[str, list[str]]] = []  # (label, hard error lines)

    for path in files:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        blocks = extract_blocks(text)
        for i, block in enumerate(blocks, 1):
            total_blocks += 1
            if is_illustrative_fragment(block):
                skipped += 1
                if args.verbose:
                    print(f"SKIP  {os.path.relpath(path, REPO_ROOT)} block #{i} "
                          f"(illustrative 'before'/pseudocode)")
                continue
            target = detect_target(text, block)
            hard, conc, dropped = typecheck_block(block, target)
            label = f"{os.path.relpath(path, REPO_ROOT)} block #{i} [{target.sdk}]"

            fail_here = bool(hard) or (args.strict_concurrency and bool(conc))
            if fail_here:
                failing += 1
                shown = hard + ([f"[concurrency] {c}" for c in conc] if args.strict_concurrency else [])
                fail_details.append((label, shown))
                print(f"FAIL  {label}")
                for line in hard:
                    print(f"        {line}")
                if args.strict_concurrency:
                    for line in conc:
                        print(f"        [concurrency] {line}")
            elif conc:
                concurrency_only += 1
                print(f"WARN  {label}  ({len(conc)} concurrency diag(s); "
                      f"run --strict-concurrency to enforce)")
                if args.verbose:
                    for line in conc:
                        print(f"        [concurrency] {line}")
            elif args.verbose:
                print(f"PASS  {label}"
                      + (f"  ({len(dropped)} stub diags ignored)" if dropped else ""))

    summary = (
        f"Checked {total_blocks} block(s) across {len(files)} file(s): "
        f"{failing} failure(s), {concurrency_only} with concurrency warnings, "
        f"{skipped} illustrative skipped."
    )
    print(f"\n{summary}")
    _write_github_summary(summary, fail_details)
    return 1 if failing else 0


def _write_github_summary(summary: str, fail_details: list[tuple[str, list[str]]]) -> None:
    """Append a markdown report to the GitHub Actions job summary, if running in CI."""
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = ["## Swift type-check", "", summary, ""]
    if fail_details:
        lines.append("### Failures")
        for label, errs in fail_details:
            lines.append(f"- **{label}**")
            for e in errs:
                lines.append(f"  - `{e}`")
    else:
        lines.append("✅ No compile failures.")
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        pass


if __name__ == "__main__":
    sys.exit(main())
