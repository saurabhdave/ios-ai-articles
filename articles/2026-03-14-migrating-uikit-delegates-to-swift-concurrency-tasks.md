# Migrating UIKit Delegates to Swift Concurrency Tasks

Delegate methods are everywhere in UIKit — table views, text fields, location updates, AV callbacks. They work, but callback-heavy flows and tight coupling to object lifecycles make composition, cancellation, and reasoning harder as an app grows. Swift Concurrency (async/await, Task, AsyncStream) gives you structured cancellation and clearer control flow; the trick is migrating incrementally and safely.

This article shows a pragmatic, production-focused approach: build small adapters that bridge delegates to async/await, migrate view-scoped flows first, and validate with tests and observability. The goal is safer, more composable UI code without surprising behavioral changes for users.

> Start small: migrate view-scoped delegates first, instrument heavily, and make the adapter the single source of truth for that flow.

## Why this matters now
UI code is often the last place teams adopt structured concurrency because lifecycle and availability concerns are hardest there. Moving delegate flows to Task-oriented adapters reduces nested callbacks and gives you explicit cancellation via Tasks, but it also changes observable behavior and can introduce rollout risk.

- When to act: start with view-scoped delegates and screen-scoped flows where lifecycle boundaries are clear.
- What to expect: changes to cancellation behavior, timing differences, and the need for platform availability guards.
- Operational note: add logging and lightweight tracing around adapters to detect missed completions or leaked Tasks.

Migrate the adapter, not the whole app: make the adapter the single source of truth for a delegate flow so you avoid double-delivery and lifecycle mismatches.

## 1. PLAN THE MIGRATION: INVENTORY, PRIORITIZATION, COMPATIBILITY
### Map delegate touchpoints
Create a concrete inventory of delegate usages: UITableViewDelegate, UITextFieldDelegate, CLLocationManagerDelegate, AV player outputs, etc. Use code search, inspect storyboards/nibs, and add runtime checks where helpful to find delegate assignments made in Interface Builder.

Decision guidance:
- Stream of events → AsyncStream or AsyncThrowingStream.
- One-shot response → async function returning a value or throwing an error.

Operational/testing note:
- Add unit tests asserting delegate registration state. Instrument adapters to assert attach/detach so you can detect missing or duplicated registrations early.

### Prioritize by risk and ROI
Migrate components with clear lifecycle ownership first:
- Prefer view-scoped Tasks: start work when a view appears and cancel when it disappears.
- Defer long-lived singletons or shared managers until you have clear cancellation and reconciliation strategies.

Compatibility:
- Guard concurrency API calls with runtime availability checks if you support older OS versions.
- For older platforms, consider a mixed adapter that falls back to delegate-based semantics; ensure only one path emits events to avoid duplication.

## 2. ADAPTER PATTERNS: BRIDGING DELEGATES TO ASYNC/AWAIT
### Build small, testable adapter objects
Implement an adapter that owns delegate conformance and exposes async APIs. Responsibilities:
- Expose AsyncStream/AsyncThrowingStream for ongoing event streams.
- Expose async functions for one-shot flows (e.g., await authorization).
- Own and manage delegate registration to avoid duplication.
- Translate delegate callbacks into stream yields or resume continuations.
- Provide explicit cancellation/cleanup handlers to unregister delegates and stop listeners.

Decision guidance:
- AsyncStream: ordered sequence of values where throwing isn’t expected.
- AsyncThrowingStream: sequence where errors may occur and should be surfaced.
- Single async func: for delegate patterns producing a single response.

Operational note:
- Ensure Task cancellation propagates into the adapter: canceling the Task should unregister delegates and stop native listeners. Record cancellation events in logs or traces.

### Testing adapters in isolation
- Unit-test adapters with deterministic fake delegate triggers.
- Use XCTestExpectation to wait for stream emissions and assert cancellation behavior.
- Validate that adapter cleanup removes delegate references to avoid retain cycles.

## 3. LIFECYCLE AND TASK SCOPE
### View-scoped vs long-lived tasks
- View-scoped Tasks: start when the view appears and cancel on disappear/dismiss. These are easier to reason about and safer for UI updates.
- Controller- or app-scoped Tasks: need reconciliation strategies and strong cancellation semantics before migration.

Practical guidance:
- Attach Task cancellation to lifecycle callbacks (viewDidAppear/viewDidDisappear or lifecycle publishers in modern APIs).
- Avoid Tasks that outlive their owners. If a Task must outlive a view, ensure it communicates state via a weakly referenced coordinator or a value-based model.

## 4. TRADEOFFS AND PITFALLS
### Practical tradeoffs
- High-frequency callbacks (audio/video frames, sensor ticks) may not map cleanly to AsyncStream without scheduling or latency tradeoffs. For low-latency processing, keep native delegate paths and expose higher-level state via concurrency.
- Mixed observation systems increase synchronization complexity. Prefer modern observation APIs when available.

Common pitfalls:
- Lifecycle mismatches: Tasks outliving owners and updating deallocated views. Always cancel view-scoped Tasks at appropriate points.
- Duplicate emissions: leaving the original delegate active alongside the adapter can double-deliver events. Ensure the adapter controls delegate registration.
- Availability mistakes: calling concurrency APIs without runtime checks may crash on unsupported platforms.

Operational/testing note:
- Add tests that explicitly exercise dismissal/cancellation paths.
- Profile main-thread timing to catch unexpected scheduling impacts.

## 5. VALIDATION, OBSERVABILITY, AND ROLLOUT
### Test strategy
- Unit tests: target the adapter boundary. Verify stream yields and deterministic cancellation.
- Integration/UI tests: exercise cancellation paths (dismiss view while a Task is in flight) and check for main-thread violations.

Observability:
- Add logging or signposts around adapter creation, event emission, and cancellation. Correlate traces with profiling during rollout.
- Track metrics: unexpected completions, cancellation counts, and duplicate emission counts.

Rollout guidance:
- Gate risky migrations behind a feature flag and staged rollout.
- Monitor crash reports, responsiveness, and custom metrics. Be ready to disable the adapter quickly if metrics regress.

## 6. PRACTICAL CHECKLIST BEFORE MERGE
- Inventory: all storyboard and programmatic delegate assignments mapped.
- Adapter: AsyncStream/AsyncThrowingStream adapters implemented with explicit cancel handlers where appropriate.
- Lifecycle: view-scoped Tasks cancel at appropriate lifecycle points; adapters do not hold strong references to views/controllers.
- Compatibility: runtime availability checks and fallbacks in place.
- Tests: unit tests for adapters; UI/integration tests for cancellation and ordering.
- Observability: logging, traces, and a plan to track task cancellation vs unexpected completion.
- Rollout: feature flag and staged rollout with monitoring.

- Quick scan list:
 - Inventory complete
 - Adapter implemented and unit-tested
 - Lifecycle/cancellation validated
 - Instrumentation and rollout gate added

## Closing takeaway
Migrating UIKit delegates to Swift Concurrency yields clearer code and structured cancellation, but do it incrementally. Treat adapters as the migration boundary: use AsyncStream for multi-value flows and async functions for one-shot callbacks, guard with availability checks, validate with focused tests, and monitor rollout. Small, well-instrumented steps beat a big-bang rewrite every time.

## Swift/SwiftUI Code Example

_No validated code snippet was generated this run._

## References

- No verified external references were available this run.
