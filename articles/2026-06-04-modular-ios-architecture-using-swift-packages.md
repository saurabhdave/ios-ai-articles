# Modular iOS Architecture Using Swift Packages

A cosmetic refactor that widens visibility can unintentionally expose helper types and increase runtime coupling between app binaries. This piece focuses on pragmatic decisions when migrating code into Swift Package Manager packages: how to design package APIs, size build units, observe regressions, and stage rollouts so teams reduce the blast radius of small changes.

## Why This Matters For iOS Teams
Monolithic Xcode projects can tie unrelated work together: a single change may touch UI wiring, feature logic, and CI, increasing feedback time. When code is copied or moved into packages without discipline, teams often make many symbols `public` to enable reuse; that expands the long-lived API surface and the potential compatibility blast radius.

Exposed ABI surface causes problems when refactors change symbols or when mixed-version combinations appear in the field. Modularization reduces coupling only when package boundaries, API-stability checks, package-scoped tests, and observability tied to package releases are defined up front.

## 1. Module Boundaries And Public API Design
### Define a Narrow Public Surface
Choose `internal` visibility by default when you are iterating quickly on behavior; choose a small, reviewed public facade when multiple apps or teams depend on a stable contract. Use an `internal import` (the Swift 6 access-level import that supersedes the deprecated `@_implementationOnly`) for implementation dependencies you do not want in the ABI, and require an API-stability review before making a type or function `public`.

Add CI checks that validate intended changes to the public surface and validate public contract changes with package-scoped `XCTest` suites. Stage rollouts behind runtime feature flags so clients can opt in from a small cohort first. Treat every public change as a compatibility decision and include automated checks in CI that exercise the public surface.

Example facade that hides private helpers and keeps a dependency out of the ABI:

```swift
import Foundation
internal import CryptoKit

public struct AuthToken: Sendable, Codable {
    public let token: String
    public let expiresAt: Date

    public init(token: String, expiresAt: Date) {
        self.token = token
        self.expiresAt = expiresAt
    }

    public func signedRepresentation() -> String? {
        // Implementation uses CryptoKit, but the `internal import` keeps CryptoKit
        // out of this module's public ABI.
        guard let data = try? JSONEncoder().encode(self) else { return nil }
        let digest = SHA256.hash(data: data)
        return digest.map { String(format: "%02x", $0) }.joined()
    }
}
```

## 2. Package Structure, Build Performance, And Compilation Units
### Group Targets For Incremental Work, Not Maximum Reuse
Choose many tiny targets when independent teams own separate lifecycles or CI caching reliably reuses intermediate artifacts; choose larger grouped targets when CI metadata churn or dependency-resolution overhead slows builds. Measure local and CI build times before and after splitting targets and prefer larger targets if many small targets increase overall wall-clock build time.

Use `@inlinable` only when you need cross-module inlining for a hot path and accept the ABI and compilation implications; profile hot paths on representative devices to justify `@inlinable` usage. Preserve `Package.resolved` in source control and validate CI agents' cache configuration to reduce fragility. Tune CI caching and parallelism to match the target graph; if caches are frequently cold or `Package.resolved` differs across agents, many small targets can slow down builds.

## 3. Validation, Testing, And CI Integration
### Encode Async Contracts Into Package Tests
Choose deterministic, continuation-based tests when you rely on concurrency invariants; choose integration tests only for end-to-end validation. Unit `XCTest` contract tests per package should cover deterministic async boundaries and edge cases so you can detect races before release.

When relying on concurrency, write deterministic tests that assert continuation and cancellation behavior rather than relying solely on live network integration tests. Integration tests are valuable for end-to-end validation but should not be the only safety net; flaky tests reduce trust in CI and can mask races that only appear on specific devices or under load.

Concrete snippet for deterministic async testing:

```swift
func testAsyncSequenceCompletes() async throws {
    let expectation = XCTestExpectation(description: "async contract")
    let system = MyPackageService()

    Task {
        do {
            try await system.performCriticalWork()
            expectation.fulfill()
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    // In an async test, await fulfillment; wait(for:timeout:) is marked noasync.
    await fulfillment(of: [expectation], timeout: 5.0)
}
```

Add package-scoped `XCTest` suites that exercise API contracts and concurrency paths and tie them into CI so package-level regressions are visible independently of app integration tests. Validate cancellation paths before rollout; a task that cannot be cancelled leaks CPU and battery.

## 4. Dependency Management, Versioning, And Release Strategy
### Pin Versions, Commit Lockfiles, Gate Rollouts
Choose strict version pinning when you require predictable builds and controlled rollouts; choose looser ranges for rapid experimentation where consumers accept instability. Commit `Package.resolved` to source control and prefer semantic-versioned releases for packages that need stability.

Gate runtime behavior with feature flags and map package releases to staged rollouts: enable features for a canary cohort before widening. If you distribute binaries via `XCFramework`, preserve symbol information and map releases to rollout gates because distributing binaries can obscure profiling signals compared to source packages. Combine package version pins with feature-flagged rollouts to mitigate mixed-version states in the field and validate regressions via canary cohorts.

## 5. Observability And Instrumentation
### Instrument Packages, Not Just The App
Choose signposts and structured logging in packages when you need package-level attribution for regressions; choose minimal instrumentation when telemetry capacity is constrained to avoid noise. Add `os_signpost` at async boundaries and structured logs for critical paths so traces can attribute CPU and allocation regressions to a package.

When package source is available, Instruments can correlate CPU and allocation changes to package-level signposts; distributing only binaries reduces that signal. Emit structured logs (JSON or keyed fields) to enable server-side filtering and quick triage of user-visible failures. Collect post-release signals with platform telemetry and make rollouts contingent on those metrics. Treat the package boundary as a product interface: every public API decision, test, and signpost matters for rollback and forensics.

> Treat every public API change like a release: it affects rollbacks, profiling, and downstream diagnostics.

## Tradeoffs And Pitfalls
Modularization increases coordination overhead: more packages mean governance, stable branching policies, and API review discipline. Isolation reduces blast radius but adds ABI crossings and potential runtime cost from extra boundary calls; that cost can be measurable in tight loops or high-call-rate hot paths on some devices.

Mixed-version states in the field are a migration risk; combine package version pins with feature-flagged rollouts to mitigate it. CI fragility often stems from inconsistent `Package.resolved`; commit it and validate CI agents' cache configuration. Be mindful that distributing binaries can obscure profiling signals and complicate root-cause analysis.

## Validation & Observability
- Add package-scoped `XCTest` suites that exercise API contracts, async behavior, and edge cases using deterministic async patterns such as continuation-based tests.
- Mark async boundaries with `os_signpost` so Instruments' profiler and allocation tools can attribute regressions to specific packages.
- Emit structured logs (JSON or keyed fields) to enable server-side filtering and fast triage of failures.
- Collect post-release signals with platform telemetry and make rollouts contingent on those metrics.
- Gate every package rollout with a canary cohort behind a runtime feature flag and monitor traces and metrics before widening.

## Practical Checklist
- [ ] Identify logical package boundaries and list public APIs to stabilize before migration.
- [ ] Add package-scoped `XCTest` suites covering API contracts, async behavior, and edge cases.
- [ ] Commit `Package.resolved` and enable CI caching for swift build artifacts.
- [ ] Add `os_signpost` signposts and structured logging in critical async paths; add platform telemetry metrics for rollout monitoring.
- [ ] Create a semantic-versioning policy and a staged rollout checklist tied to feature flags.
- [ ] Convert one candidate feature to a SwiftPM package behind a feature flag; validate via a canary rollout before broad adoption.

## Closing Takeaway
Move one feature at a time and treat the package boundary as a product interface: define a narrow public API, verify it with package-scoped tests, instrument with signposts and structured logs, and roll out behind a flag. Discipline around API surface, committed lockfiles, and staged rollouts determines whether modularization accelerates teams or multiplies toil. Start small, measure regressions with traces and metrics, and pin versions before scaling.

## Swift/SwiftUI Code Example

```swift
import Foundation
import SwiftUI
import Observation

@MainActor public protocol FeatureProviding {
    var count: Int { get }
    func increment() async -> Int
}

@MainActor
@Observable
internal class InternalCounter: FeatureProviding {
    var count: Int = 0
    func increment() async -> Int {
        count += 1
        return count
    }
}

public enum Feature {
    @MainActor public static func make() -> FeatureProviding { InternalCounter() }
}

public struct CounterView: View {
    @State private var count: Int
    private let provider: FeatureProviding

    @MainActor public init(provider: FeatureProviding = Feature.make()) {
        self.provider = provider
        self._count = State(initialValue: provider.count)
    }

    public var body: some View {
        VStack(spacing: 12) {
            Text("Count: \(count)")
            Button("Increment") {
                Task { count = await provider.increment() }
            }
        }
        .padding()
    }
}
```

## References

- [What's new in Swift: May 2026 Edition](https://swift.org/blog/whats-new-in-swift-may-2026/)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
