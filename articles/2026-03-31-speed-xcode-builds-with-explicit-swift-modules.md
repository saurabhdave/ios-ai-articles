# Speed Xcode Builds with Explicit Swift Modules

Builds that are fast locally but slow on CI break review velocity and increase context switching. I frequently see intermittent `module is out of date` or obscure type‑checking failures when prebuilt `.swiftmodule` artifacts are reused across different Xcode or toolchain images. This note explains how generating explicit Swift module artifacts reduces repeated parsing and type‑checking work and what teams should control when adopting them.

## Why This Matters For iOS Teams

Slow incremental builds reduce developer throughput, especially when a repository contains many interdependent frameworks and mixed Objective‑C/Swift interop. Parsing headers and re‑type‑checking public symbols can dominate wall time; generating explicit module artifacts and consuming prebuilt ` .swiftmodule` files reduces repeated parsing when the build environment is reproducible and caches are validated.

If CI cannot guarantee consistent compiler or toolchain images, or the team lacks bandwidth to manage cache invalidation, building from source remains a reasonable choice. Choose explicit modules when incremental build time dominates review latency and your CI can produce reproducible artifacts; choose source builds when toolchain variance or maintenance overhead outweighs caching benefits.

> Prebuild modules that are auditable by checksum and toolchain ID; a single mismatch explains many intermittent type‑checking failures.

## 1. What Explicit Swift Modules Means For Your Build

### Prebuild And Consume Workflow
The preferred approach is to prebuild framework modules into explicit `.swiftmodule` artifacts and have downstream compiles restore and consume them directly instead of recompiling from source on every job with `xcodebuild`. Use `xcodebuild` in the prebuild job to produce module artifacts and store the produced `.swiftmodule` files alongside a signed checksum and toolchain identifier.

Choose prebuilt modules when dependency graphs are large and the same artifacts will be consumed across many downstream jobs; choose per‑commit source builds when artifacts cannot be reproduced across runners. Validate the workflow by running a canary pipeline that restores modules and attempts a clean rebuild from source to verify checksum equivalence and fail fast on mismatch. Include a toolchain identifier and content checksum in cache keys to prevent cross‑toolchain reuse, since reusing stale `.swiftmodule` files from a different toolchain image causes subtle failures.

Operationally, add a CI verification job that restores a pristine runner, builds modules from source, computes checksums, and compares them to cached artifacts so mismatches fail early instead of surfacing as intermittent type errors later.

## 2. How To Organize Frameworks And Module Interfaces

### Strict Module Boundaries Over Public Leaks
A common shortcut when prebuilding modules is to make many types public to avoid visibility errors. Prefer a concise set of public APIs, use `DEFINES_MODULE` where appropriate, and when Objective‑C interop is required, control exposure with an explicit `Module.modulemap`. Enforce an API review process and require a rationale for each new public symbol in PR templates.

Choose strict API boundaries when multiple teams or binary frameworks consume the artifact; choose a more permissive surface when a quick experimental rollout is required but gate that with a canary pipeline and short expiry caches. Add a CI check that flags unexpected increases in public symbols and add codeowners for the module’s public headers to catch accidental leaks. Test cancellation and rollback paths as part of the canary so CPU or queue leaks do not occur during migration.

## 3. CI Cache Keys, Invalidation And Verification

### From Branch Keys To Content‑Addressed Keys
Caching intermediate artifacts with a single branch key leads to cache poisoning. Construct cache keys from content‑addressable pieces: dependency file checksums, compiler/toolchain identifiers, and build settings that affect module output. When caching cross‑commit artifacts, prefer checksum‑based keys; when dependency churn is high within a PR, use ephemeral or per‑run caches.

Choose checksum‑based cache keys when artifacts are intended for reuse across commits; choose ephemeral caches when churn makes verification costlier than rebuilding. Add structured logs for cache hits and misses and include the cache key components so each cached module ties back to a checksum, a toolchain ID, and a commit hash for reproducibility and debugging. Fail the pipeline on checksum mismatch to avoid subtle type‑checking errors later.

Include read/write logs and cache key components in CI build artifacts so engineers can audit and trace failures without rerunning expensive builds.

## 4. Rollout, Testing And Observability

### Gate Changes With Traces And Signposts
Roll out explicit modules behind a canary CI pipeline and gate expansion with deterministic checks. Use profiler traces to compare parsing and type‑checking hot paths before and after rollout and set team baselines that fail the job when regressions exceed your threshold.

Emit signposts from build helper tooling to mark prebuild boundaries and aggregate traces in your telemetry backend. Use `OSSignposter` and structured logging to record cache operations and to correlate traces to specific artifacts. Standardize CI agent images because noisy or non‑reproducible runners make observability signals hard to interpret. Test cancellation, failure handling, and migration rollback paths in the canary to avoid prolonged CPU consumption or queue stalls.

```swift
import Foundation
import OSLog

@MainActor
final class BuildSignposter {
    private let signposter = OSSignposter(subsystem: "com.company.ci", category: "module-build")
    private var interval: OSSignpostIntervalState?

    // OSSignposter has no `emit`; mark boundaries with beginInterval/endInterval
    // and keep the returned state to close the interval.
    func markPrebuildStart() {
        interval = signposter.beginInterval("PrebuildModule")
    }

    func markPrebuildEnd(info: String) {
        guard let interval else { return }
        signposter.endInterval("PrebuildModule", interval, "info: \(info, privacy: .public)")
        self.interval = nil
    }
}

// Usage from a main-actor context:
@MainActor
func runPrebuild() {
    let buildSignposter = BuildSignposter()
    buildSignposter.markPrebuildStart()
    // run prebuild step...
    buildSignposter.markPrebuildEnd(info: "success")
}
```

## Tradeoffs And Pitfalls

Explicit modules reduce parsing and type‑check work on parsing‑heavy CI workloads but increase operational complexity. Common pitfalls include cache poisoning when keys omit compiler or build identifiers, hidden API churn when teams make internals public to fix build errors, and reusing artifacts produced by a different toolchain image causing subtle compilation or type‑checking failures.

Mitigate these by locking cache keys, enforcing API review, and running a clean‑rebuild CI job on every cache write. If your repo is small and has few frameworks, explicit modules may add maintenance overhead with limited benefit — measure before committing. Monitor for accidental public symbol growth and add codeowners for public headers to keep the surface area explicit.

## Validation And Observability

### Tests, Traces And Auditability
Add tests that assert prebuild and consume steps complete within team‑defined baselines and fail on regressions. Capture profiler traces on representative CI agents and local machines to identify hot parsing and type‑checking paths and compare before/after rollout.

Tie each cached module to a checksum, a toolchain identifier, and a commit hash so a single reproducible run can explain how an artifact was produced. Fail canary runs on checksum mismatches or trace regressions and retain profiler traces with build metadata for post‑mortem analysis. Collect and store traces, signposts from `OSSignposter`, and structured cache logs in your telemetry backend so engineers can triage failures without rerunning costly builds.

- Collect and store profiler traces with build metadata.
- Fail canary runs on checksum or trace regressions.
- Make cache keys auditable and human‑readable for quicker triage.

## Practical Checklist

- [ ] Audit public interfaces and restrict public symbols; require API review and codeowners for changes.
- [ ] Enable explicit module generation in a feature branch; measure baseline builds locally and on CI.
- [ ] Add regression checks for build steps and collect profiler traces pre/post change.
- [ ] Build cache keys from dependency checksums and compiler/toolchain identifiers; add cache‑verification CI jobs.
- [ ] Roll out via a canary CI pipeline and monitor structured logs and `OSSignposter` metrics for regressions.
- [ ] Document module build rules, troubleshooting steps for stale `.swiftmodule` issues, and a rollback plan.

## Closing Takeaway

Generating and consuming explicit Swift module artifacts reduces repeated parsing and type‑checking work in large repositories with many internal frameworks and reproducible CI environments. Measure impact before changing, gate rollout with a canary pipeline, make cache keys auditable by including checksums and toolchain identifiers, and enforce API discipline to limit long‑term maintenance cost. When toolchain reproducibility or team bandwidth is lacking, prefer source builds until those constraints are resolved.

## Swift/SwiftUI Code Example

```swift
import SwiftUI

struct ExplicitModulesHelperView: View {
    let target: String
    let configuration: String

    init(target: String = "MyFramework", configuration: String = "Release") {
        self.target = target
        self.configuration = configuration
    }

    // Produce recommended XCBuild / xcodebuild flags to emit explicit Swift modules
    func xcodebuildCommands(for scheme: String) -> [String] {
        [
            // Build a reproducible framework and emit module interface + swiftmodule
            "xcodebuild -scheme \(scheme) -configuration \(configuration) BUILD_LIBRARY_FOR_DISTRIBUTION=YES OTHER_SWIFT_FLAGS='-emit-module -emit-module-path ${BUILT_PRODUCTS_DIR}/\(target).swiftmodule -emit-module-interface-path ${BUILT_PRODUCTS_DIR}/\(target).swiftinterface' SKIP_INSTALL=NO",
            // Archive the built framework for CI cache / artifact storage
            "xcodebuild -scheme \(scheme) -configuration \(configuration) archive -archivePath ./archives/\(scheme).xcarchive SKIP_INSTALL=NO BUILD_LIBRARY_FOR_DISTRIBUTION=YES"
        ]
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Explicit Swift Modules")
                .font(.headline)
            Text("Recommended xcconfig entries:")
                .font(.subheadline)
            Group {
                Text("BUILD_LIBRARY_FOR_DISTRIBUTION = YES")
                Text("DEFINES_MODULE = YES")
                Text("SWIFT_ENABLE_EXPLICIT_MODULES = YES")
            }
            .font(.system(.caption, design: .monospaced))
            .foregroundColor(.secondary)
            if let cmd = xcodebuildCommands(for: target).first {
                Text("Example xcodebuild:")
                    .font(.subheadline)
                Text(cmd)
                    .font(.system(.caption, design: .monospaced))
                    .foregroundColor(.blue)
            }
        }
        .padding()
    }
}
```

## References

- [What's new in Swift: March 2026 Edition](https://swift.org/blog/whats-new-in-swift-march-2026/)
- [Xcode 26.5 beta (17F5012f)](https://developer.apple.com/news/releases/?id=03302026g)
- [VoiceOver Navigator & 120 FPS Recordings for Xcode’s Simulator](https://www.avanderlee.com/xcode/voiceover-navigator-120-fps-recordings-for-xcode-simulator/)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
