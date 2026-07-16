# Speed Up Xcode Builds with Explicit Modules

Xcode says “Compiling Swift” even when your diff barely touched anything. If your workspace mixes Swift with large Objective‑C headers, those spins are usually `swiftc` and `Clang` reparsing the world. Make modules explicit and you prebuild once, then reuse.

> Precompile the graph once, and avoid paying parsing costs in every file—explicit modules can turn random rebuilds into more deterministic work.

*All code in this article targets iOS 26+ and Swift 6.2 unless noted otherwise.*

## Why This Matters For iOS Teams

Build minutes are a budget. Slow builds block PRs, delay hotfix SLAs, and complicate coordinated releases across multiple apps and SDKs. On CI runners with parallel jobs, small regressions multiply into missed windows. In mixed Swift/Objective‑C projects with broad header surfaces, explicit modules cut redundant front‑end work by reducing duplicate parsing and stabilizing the dependency graph. The tradeoff is migration effort: header hygiene, module map fixes, and cache strategy.

## 1. What Explicit Modules Change In The Build Pipeline

### Before: Ad‑Hoc Parsing; After: Deterministic Prebuilds

By default, the driver discovers dependencies implicitly. Each Swift file may traverse the bridging header, and `Clang` may build modules implicitly. Large transitive C/Objective‑C header trees magnify this cost. With explicit modules, the driver computes a dependency graph up front and prebuilds each module once. That work is then reused across targets and files, so you pay parsing costs predictably.

```swift
#if canImport(PackageDescription)
import PackageDescription

let package = Package(
    name: "MyPackage",
    platforms: [
        .iOS(.v18)
    ],
    products: [
        .library(name: "Networking", targets: ["Networking"])
    ],
    targets: [
        .target(
            name: "Networking",
            path: "Sources/Networking",
            swiftSettings: [
                .unsafeFlags(["-explicit-module-build"], .when(configuration: .release))
            ]
        )
    ]
)
#endif```

Choose explicit module builds when targets expose deep C/Objective‑C headers or are reused widely across the workspace; choose implicit builds when a target is tiny, Swift‑only, and compiles in milliseconds. Expect your first enablement to surface “Include of non‑modular header inside framework module.” Treat that as a cue to audit umbrella headers and module maps rather than a reason to revert.

### The Sharp Edge: Non‑Modular Includes

This error appears when public headers import files outside the declared module or when private headers leak into public surfaces. It can reproduce only under parallel builds on CI due to header search path differences, so reproduce with `xcodebuild` locally using the same `HEADER_SEARCH_PATHS` as CI before rollout to the rest of the tree.

```swift
// Represent a module map as a Swift string to validate its contents in a prebuild script.
let moduleMap = """
module MyCLib [system] {
  umbrella header "MyCLib.h"
  export *
  module * { export * }
}
"""
// Write to $(SRCROOT)/MyCLib/module.modulemap after verifying headers exist.
```

## 2. Enabling Explicit Modules In Xcode And SwiftPM

### Start With Leaf Frameworks, Then Move Up

Flipping “Build with Explicit Module” across everything at once can trigger a flood of modularity failures and noisy triage. Prefer a staged rollout: 1) enable per target starting with leaf frameworks (no dependents), 2) move up to middle‑tier libraries, 3) flip top‑level app targets last, and 4) roll by configuration—`Release` and CI first; `Debug` after headers are clean.

```swift
// Xcode: ALSO add the driver flag to make intent explicit.
let flags = ["-explicit-module-build"] // OTHER_SWIFT_FLAGS on the target
// SwiftPM on CI: swift build -Xswiftc -explicit-module-build
// Keep the flag scoped to Release until headers are clean.
```

Choose per‑target enablement when you want to isolate failure domains and avoid blocking app builds; choose workspace‑wide enablement only after the majority of targets are clean and you can afford coordinated fixes. Document which targets are opted in and why, so later refactors don’t silently flip settings and reintroduce flakes.

### CI Cache Stabilization

A warm cache that isn’t the same cache doesn’t help. Cache churn from toolchain drift or volatile paths can erase wins. Pin the exact Xcode toolchain across runners, keep a stable `DerivedData` root per branch or workspace, and dedicate a shared cache for third‑party frameworks when appropriate.

```swift
// Stable DerivedData path strategy resolved from CI environment.
let env = ProcessInfo.processInfo.environment
let dd = env["DERIVED_DATA_DIR"] ?? "/Volumes/buildcache/DerivedData"
print("Using DerivedData: \(dd)")
print("Xcode: \(env["DEVELOPER_DIR"] ?? "default")")
```

Choose to align toolchain versions when warm builds run slower than cold builds on the same runner class; choose to rebuild once across the fleet when invalidation storms appear after a toolchain bump.

## 3. Header Hygiene And Module Maps

### Tighten Umbrella Headers

Your umbrella header should include only headers that are part of the module. Avoid reaching across into other frameworks or private directories. When consumed by Swift targets, mismatched header search paths often bite only on CI; replicate CI’s `xcodebuild` invocation locally to validate the exact `HEADER_SEARCH_PATHS`.

```swift
// Minimal umbrella include validator (Run Script phase).
import Foundation
let umbrella = URL(fileURLWithPath: "Sources/MyCLib/include/MyCLib.h")
let lines = (try? String(contentsOf: umbrella).split(separator: "\n")) ?? []
let bad = lines.filter { $0.trimmingCharacters(in: .whitespaces).hasPrefix("#include") && ($0.contains("../") || $0.contains("<")) }
if !bad.isEmpty { fputs(bad.joined(separator: "\n") + "\n", stderr); exit(1) }
```

Choose a `module.modulemap` to expose only the public surface when you need to hide private headers; choose umbrella‑only exposure when the public surface is already minimal and self‑contained.

### Fix Non‑Modular Includes With Module Maps

Use a `module.modulemap` to declare your public surface and hide private details. Ensure transitive dependencies are themselves proper modules; otherwise, create module maps for them or isolate their usage behind your module’s headers.

```swift
// Generate a minimal module map for a C dependency during a prebuild step.
let publicHeaders = ["Foo.h", "Bar.h"].map { "  header \"\($0)\"" }.joined(separator: "\n")
let map = """
module VendorLib {
\(publicHeaders)
  export *
}
"""
try? map.write(to: URL(fileURLWithPath: "VendorLib/module.modulemap"), atomically: true, encoding: .utf8)
```

Choose to author a vendor module map when a third‑party library lacks one and is imported transitively by Swift; choose to isolate or fork the dependency when its header sprawl makes modularization impractical for your timeline.

## 4. Build Artifacts, Stability, And Reuse

### Build Once, Consume Across Toolchains

When multiple apps consume the same frameworks, pair explicit modules with module stability. Enable `BUILD_LIBRARY_FOR_DISTRIBUTION` to emit `.swiftinterface` files and include them in a distributed `.xcframework`. Tag artifacts with the toolchain version and validate at least one downstream consumer before a broader rollout to catch import mismatches early.

Choose shipping stable binary frameworks when you have many consumers or separate toolchain cadences; choose source consumption when you need rapid iteration and the frameworks are small enough that rebuilds don’t dominate.

### Deterministic Dependency Resolution

Explicit prebuilds serialize key work early. One large framework’s prebuild can become the critical path when the framework exposes a wide public header surface. If overall time regresses, check whether a single prebuild stalls the graph; refactor that module’s public surface or reduce header fan‑out before enabling more targets.

```swift
// Minimal Process runner to capture xcodebuild timing in a CI utility binary.
import Foundation

let task = Process()
task.launchPath = "/usr/bin/xcrun"
task.arguments = ["xcodebuild", "-workspace", "App.xcworkspace", "-scheme", "App", "-showBuildTimingSummary"]
let pipe = Pipe(); task.standardOutput = pipe
task.launch(); task.waitUntilExit()
let output = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
print(output)
```

Choose to narrow a framework’s public headers when it blocks concurrency; choose to split or internalize headers when the public surface can’t be trimmed without breaking dependents.

## 5. Debugging And Rollout Strategy

### Choose Targets Deliberately

Flip the flag only where it pays back. Targets that are small, Swift‑only, and not reused widely often won’t benefit. When a target’s headers are deep and reused by multiple dependents, enable explicit modules; when a target compiles quickly and has no C/Obj‑C surface, keep implicit modules. Keep `Debug` off at first so engineers can iterate while modularity issues are resolved in `Release` and CI; once headers are clean, enable `Debug` so local builds match CI behavior.

### Observability As You Roll

Instrument custom prebuild steps with `OSSignposter` and `Logger` to mark boundaries in build logs. When a timing spike appears, identify whether it was dependency resolution, prebuild, or compilation. If you have build tooling that runs outside Xcode (for example, as part of `xcodebuild` pre‑actions), keep those markers—Instruments can surface them in the timeline when diagnosing regressions.

```swift
import OSLog

let log = Logger(subsystem: "com.yourorg.build", category: "metrics")
let signposter = OSSignposter(logger: log)

let state = signposter.beginInterval("Prebuild: GenerateModuleMap")
defer { signposter.endInterval("Prebuild: GenerateModuleMap", state) }

// … Run generation logic, file IO, validations …
```

Choose to gate rollout behind metrics when multiple teams share the workspace; choose an ad‑hoc rollout only when the blast radius is limited to a single leaf target.

## Tradeoffs And Pitfalls

- Migration cost is non‑trivial. Spend time on umbrella headers and module map correctness. Treat surfaced errors as a to‑do list, not regressions.
- Cache invalidation can erase gains. Volatile `DerivedData` paths or mixed toolchains across runners produce churn. Pin toolchains and stabilize cache paths.
- Parallel builds magnify small mistakes. Non‑modular includes that “work on my machine” frequently fail under CI parallelism due to divergent `HEADER_SEARCH_PATHS`.
- Not all targets benefit. The orchestration overhead exists even if the target is trivial; be selective.
- Diagnostics get louder. Explicit modules expose problems that implicit builds quietly tolerated. Expect to triage new warnings and errors.

## Validation And Observability

Treat this like a production change with a rollout plan and guardrails.

- Measure target timelines, not just aggregate wall time. `xcodebuild -showBuildTimingSummary` and Xcode’s Report Navigator Build Timeline reveal which prebuild or compile phases dominate.
- Gate on cold and warm builds. Run multiple trials to smooth variance on shared CI runners. Roll back if wall time regresses beyond your agreed threshold across consecutive runs on the same hardware class.
- Add lightweight `XCTest` smoke tests that import key frameworks from app and test bundles to catch non‑modular includes early.
- Mark custom steps with `OSSignposter` and `Logger` to separate dependency resolution, prebuilds, and compilation in logs and Instruments Time Profiler.
- Keep structured logs around CI cache hits and misses. A short JSON log from your build scripts that records toolchain, `DerivedData` path, and cache keys helps explain regressions.

## Practical Checklist

- [ ] Audit umbrella headers so public headers include only in‑module headers.
- [ ] Create or validate `module.modulemap` for every C/Objective‑C library consumed by Swift.
- [ ] Pin the exact Xcode toolchain across all CI runners.
- [ ] Stabilize `DerivedData` and module cache paths; avoid randomized segments.
- [ ] Enable “Build with Explicit Module” on a single leaf framework in `Release`.
- [ ] Add `-explicit-module-build` to that target’s `OTHER_SWIFT_FLAGS`.
- [ ] For SwiftPM, add `.unsafeFlags(["-explicit-module-build"], .when(configuration: .release))` to selected targets.
- [ ] Run multiple cold and warm CI builds; capture `-showBuildTimingSummary`.
- [ ] Gate rollout with thresholds; monitor target‑level timings, not just totals.
- [ ] Enable `BUILD_LIBRARY_FOR_DISTRIBUTION` on reusable frameworks and ship `.swiftinterface`.
- [ ] Validate at least one downstream consumer build before widening adoption.
- [ ] Add `OSSignposter` markers around custom prebuild steps to isolate regressions.
- [ ] Expand enablement up the dependency graph; enable `Debug` last.

## Closing Takeaway

Explicit modules move work to a predictable prebuild phase and reduce re‑parsing across files. You’ll spend effort on header hygiene, module maps, and cache strategy, but the payoff is steadier builds and fewer surprises on CI. Roll out per target and per configuration, watch target timelines, and pin your toolchain. If your app mixes Swift and Objective‑C or ships shared frameworks, this switch is often a strong default. Make the change deliberately and your team can feel the improvement in merge velocity.

## Swift/SwiftUI Code Example

```swift
import Foundation
@_implementationOnly import CryptoKit

public enum HashAlgorithm {
    case sha256
}

public struct ContentHasher {
    private let algorithm: HashAlgorithm
    public init(algorithm: HashAlgorithm = .sha256) { self.algorithm = algorithm }
    
    // Public surface is Foundation-only, so downstream modules do not depend on CryptoKit.
    public func digestHex(_ data: Data) -> String {
        switch algorithm {
        case .sha256:
            let digest = SHA256.hash(data: data)
            return hex(from: digest)
        }
    }
    
    // Keep helpers private to avoid leaking implementation details into the public ABI.
    private func hex(from digest: some Sequence<UInt8>) -> String {
        var s = ""
        s.reserveCapacity(digest.underestimatedCount * 2)
        for b in digest {
            let h = String(b, radix: 16, uppercase: false)
            if h.count == 1 { s.append("0") }
            s.append(h)
        }
        return s
    }
}
```

## References

- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
