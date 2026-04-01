# Find Swift Memory Leaks with Xcode Memory Graph

Memory growth that starts small and climbs during long sessions—until crashes or UI stutter—often signals an ownership leak rather than a rendering bug. When `NotificationCenter` observers, `Combine` subscriptions, or closure captures hold objects past their intended lifetime, you see persistent resident set growth. Use Xcode Memory Graph in a repeatable flow to confirm retention and guide targeted fixes.

## Why This Matters For iOS Teams
Memory regressions raise release risk: higher crash rates, more incidents, and urgent rollbacks when a feature drives sustained memory use. Swift’s ownership model and heavy use of closures, `Combine`, `async/await`, and delegation make capture semantics and lifecycle scoping key audit areas. Treat memory regressions like functional regressions—detect them early in CI, validate with deterministic tests, and stage rollouts to avoid wide-impact incidents.

## 1. Inspecting Objects With Xcode Memory Graph
### Snapshot Workflow And Diffing
Capture a baseline `Xcode Memory Graph` snapshot, exercise the user flow until memory grows, then capture a second snapshot and diff. Choose a single snapshot for quick pointers when you need a fast triage; choose baseline-and-diff when you must confirm persistent retention. Relying on diffs reduces false positives because some objects appear retained transiently.

Save snapshots as CI artifacts so postmortems can inspect the exact graph that triggered an alert. Validate findings with `Instruments` and deterministic XCTest reproductions before changing ownership semantics.

```swift
// Example: breaking a strong closure capture in a view controller
import UIKit

final class LoaderViewController: UIViewController {
    private var timer: Timer?

    func startPolling() {
        timer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in
            self?.fetchOnce()
        }
    }

    private func fetchOnce() {
        // network work
    }

    deinit {
        timer?.invalidate()
    }
}
```

## 2. Closure Captures, `weak` vs `unowned`, And Delegates
### Choosing Capture Semantics
Choose `weak` when the referent can become nil during the closure lifetime; choose `unowned` when the lifetime relationship is strictly hierarchical and provable. If you want to avoid crashes from unexpected deallocation, prefer `weak`. Avoid flipping every capture to `unowned` to silence warnings—audit `unowned` usage during refactors because previously-safe `unowned` references can become unsafe after changes.

For delegates, use `weak var delegate: ...` so a delegate releasing does not create a retain cycle. Add guard rails and tests that exercise delayed or retried code paths to catch lifecycle regressions caused by refactors.

Audit closures and delegation behavior in navigation and retry scenarios as part of your CI tests so fixes don’t introduce timing-based crashes.

## 3. Combine, Cancellation, And Lifecycle Scoping
### Store Cancellables With Lifecycle
Keep `AnyCancellable` values in a lifecycle-bound `Set<AnyCancellable>` and cancel them explicitly when the owning object is no longer valid. Choose a per-owner `Set<AnyCancellable>` when subscriptions are UI-related; choose global storage only for truly app-lifetime subscriptions. A global bag can accidentally retain view controllers; a per-owner set cleared in `deinit` or at a defined lifecycle point avoids that.

Cancel subscriptions in realistic lifecycle hooks and run navigation/backgrounding tests to ensure cancellation timing does not drop required work.

```swift
import Combine
import UIKit

final class FeedViewController: UIViewController {
    private var cancellables = Set<AnyCancellable>()

    override func viewDidLoad() {
        super.viewDidLoad()
        NotificationCenter.default.publisher(for: UIApplication.willEnterForegroundNotification)
            .sink { _ in /* update UI */ }
            .store(in: &cancellables)
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(_animated)
        cancellables.forEach { $0.cancel() }
        cancellables.removeAll()
    }
}
```

## 4. Fixing Notification Observers, `URLSession`, And Background Tasks
### Use Token-Based APIs And Proper Delegation
Prefer token-based `NotificationCenter` observers or remove observers in `deinit`. Choose token-based observers when you need explicit lifetime control; choose manual removal when you must support older patterns or complex lifecycle graphs. For `URLSession`, validate delegate lifecycles and prefer higher-level APIs like `URLSession.data(for:)` when they simplify ownership.

Validate cancellation and cleanup paths before rollout; uncancelled background tasks can consume CPU and battery and affect user experience. Exercise long-running background work in tests and stage rollouts when ownership semantics change.

```swift
// Pseudocode: prefer token-based observer patterns and scoped cleanup
let token = NotificationCenter.default.addObserver(forName: .myEvent, object: nil, queue: .main) { [weak self] _ in
    self?.handleEvent()
}
// store token and remove in deinit or lifecycle tear-down
```

> Use Memory Graph diffs, not single snapshots, to avoid chasing transient retention that isn’t a real leak.

## Tradeoffs And Pitfalls
Eager cleanup reduces retained memory but can increase crash surface if lifecycle assumptions are wrong. Optimizing to make a `Xcode Memory Graph` snapshot look clean can introduce timing-based brittleness that fails under different scheduling or network conditions. Changing ownership semantics can also hide a downstream race that was previously masked.

Treat a Memory Graph snapshot as a diagnostic hint, not definitive proof. Confirm ownership fixes with deterministic tests and `Instruments` traces on representative devices before rolling changes to production.

## Validation & Observability
Use automated and manual tools together. Add XCTest unit or UI tests that reproduce suspect flows and capture `Xcode Memory Graph` snapshots as CI artifacts. Complement snapshots with `Instruments` Allocations and Leaks templates to capture allocation stacks and growth trends.

Instrument async boundaries with `OSSignposter` and correlate with structured logging so production diagnostics map back to observable intervals. Run targeted `Instruments` traces on critical paths in CI and broader traces on release candidates to balance pipeline cost and diagnostic coverage.

## Practical Checklist
- [ ] Capture a baseline `Xcode Memory Graph` during a representative user flow and archive the snapshot.
- [ ] Reproduce suspected leaks with XCTest or UI tests and include Memory Graph captures in CI for regression detection.
- [ ] Audit closures, delegates, and `Combine` subscriptions; apply `weak`/`unowned` or explicit cancellation per decision criteria.
- [ ] Validate fixes with `Instruments` Allocations/Leaks on supported device families and correlate long-running flow markers using `OSSignposter`.
- [ ] Instrument key flows with structured logging and enable production diagnostics so you can detect memory regressions after staged rollouts.
- [ ] Stage rollouts with feature flags or phased releases and monitor memory-related telemetry before full deployment.

## Closing Takeaway
Xcode’s Memory Graph points to suspect ownership chains—use it in a repeatable workflow: baseline, reproduce, diff, then fix. Back ownership changes with deterministic XCTest reproductions and `Instruments` verification, and gate rollout with observability and phased deployments. Treat memory regressions as first-class regressions so long-session features do not become frequent incident sources in production.

## Swift/SwiftUI Code Example

```swift
import SwiftUI
import Observation

@MainActor
@Observable class NotificationsViewModel {
    private var token: NSObjectProtocol?
    var message: String = "Idle"

    init() {
        // Subscribe safely: capture weak self and keep the token so we can remove it
        token = NotificationCenter.default.addObserver(forName: .didReceiveDemo, object: nil, queue: .main) { [weak self] note in
            self?.message = "Received: \(note.userInfo?["text"] as? String ?? "—")"
        }
    }

    deinit {
        if let token { NotificationCenter.default.removeObserver(token) }
    }
}

extension Notification.Name { static let didReceiveDemo = Notification.Name("didReceiveDemo") }

struct NotificationsView: View {
    @State private var model = NotificationsViewModel()

    var body: some View {
        VStack(spacing: 12) {
            Text(model.message)
            Button("Post Notification") {
                NotificationCenter.default.post(name: .didReceiveDemo, object: nil, userInfo: ["text": "Hello"])
            }
        }
        .padding()
    }
}
```

## References

- [What's new in Swift: March 2026 Edition](https://swift.org/blog/whats-new-in-swift-march-2026/)
- [VoiceOver Navigator & 120 FPS Recordings for Xcode’s Simulator](https://www.avanderlee.com/xcode/voiceover-navigator-120-fps-recordings-for-xcode-simulator/)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
