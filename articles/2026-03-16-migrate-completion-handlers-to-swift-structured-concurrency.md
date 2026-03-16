# Migrate Completion Handlers to Swift Structured Concurrency

Structured concurrency (async/await) is a clearer model than nested completion handlers for many asynchronous flows — but swapping paradigms across a large, shipping codebase is risky. This guide gives a pragmatic path: identify boundaries, wrap callbacks with checked continuations, preserve cancellation, validate with tests and observability, and roll changes out safely.

## Why This Matters for iOS Teams Right Now

Async/await provides more linear control flow, clearer error propagation, and explicit task cancellation compared with deeply nested completion-handler code. For production apps, a poorly scoped migration can introduce issues that are hard to trace, such as continuations that are not resumed, underlying work that is not cancelled, or increases in resource usage.

Make migration decisions based on three pragmatic constraints: the surface area you control, how observable the layer already is, and your ability to roll back or gate behavior. Treat structured concurrency as an incremental refactor of service boundaries, not an immediate global rewrite.

## 1. IDENTIFY AND MODEL ASYNC BOUNDARIES

### Map your callback surface
Inventory where asynchronous work originates: URLSession.dataTask(with:completionHandler:), DispatchQueue.async calls that spawn work, NotificationCenter observers, Operation/OperationQueue, timers, and third‑party SDK callbacks.

- Apple API/tool: URLSession.dataTask(with:completionHandler:)
- When to choose async wrappers: wrap when the callback represents a single logical asynchronous result you can control (network fetch, file read, single SDK response).
- Operational note: map these boundaries into a simple diagram (network, disk, UI-triggered) and prioritize parts with existing telemetry.

Create a concise list of adapters you will add first:
- Service-layer network fetches
- Disk or database reads/writes
- SDK adapters you own

### Decide what to leave synchronous
Do not convert trivial forwarders or tiny synchronous callbacks that only pass values between components. Unnecessary conversion increases surface area with little benefit.

- Apple API/tool: DispatchQueue for executing legacy synchronous paths when needed
- When to keep synchronous: keep synchronous implementations for glue code that simply relays data without side effects.
- Operational note: leaving some synchronous code reduces risk and keeps rollback paths short.

## 2. BRIDGING PATTERNS AND INTEROP

### Preferred bridging approach
Use withCheckedContinuation and withCheckedThrowingContinuation to adapt single-result completion handlers into async functions. Keep the adapter small and testable.

- Apple API/tool: withCheckedThrowingContinuation
- When to choose checked continuations: prefer checked continuations for incremental migration because they help detect some misuse in debug builds.
- Operational note: add debug-only asserts and timeout instrumentation to detect double-resume or missing-resume situations during rollout.

Example strategy: add an async overload in an extension that internally uses a checked continuation, and keep the original callback API public until consumers migrate.

### Objective-C / legacy interoperability
Keep legacy completion-handler APIs available until all consumers migrate. Where safe, implement legacy APIs by calling into the new async implementation so behavior is centralized.

- Apple API/tool: Objective-C bridging and compatibility layers
- When to choose backwards compatibility: choose this path when Objective‑C consumers or third-party binaries cannot be updated concurrently.
- Operational note: include migration feature flags and telemetry to track adoption and regressions per consumer.

## 3. CANCELLATION, RESOURCE MANAGEMENT, AND RUNTIME BEHAVIOR

### Propagate cancellation aggressively
Structured concurrency exposes Task.cancel(); you must propagate that cancellation into underlying system objects like URLSessionTask or Operation.

- Apple API/tool: Task.cancel(), URLSessionTask.cancel()
- When to propagate cancellation: apply task-based cancellation for operations that can and should be interrupted (network calls, long file I/O).
- Operational note: failing to cancel underlying tasks can leave sockets or other resources open; observe runtime resource usage and task counts.

Bridge example: when your async wrapper wraps a URLSessionTask, call task.resume() and ensure the continuation resumes in all completion paths; on Task cancellation call URLSessionTask.cancel().

### Detect double-resume and missing resume
Missing resume or double-resume on continuations are common migration pitfalls.

- Apple API/tool: withCheckedContinuation (helps detect misuse in debug)
- When to use checked vs unsafe: use checked continuations for migration; only consider unsafe continuations when you can prove resume invariants and need the performance tradeoffs.
- Operational note: add unit tests that simulate cancellation, timeouts, and delayed callbacks. Use debug assertions to fail fast during CI.

Convert the boundary — not the entire codebase. Small, well-tested adapters let you observe behavior and roll back quickly if needed.

## 4. TESTING, VALIDATION, AND OBSERVABILITY

### Test strategy
Unit and integration tests must cover success, error, and cancellation paths. Stub network with URLProtocol to deterministically simulate delays, failures, and cancellations.

- Apple API/tool: XCTest expectations, URLProtocol for URLSession stubbing
- When to choose end-to-end tests: choose end-to-end network stubs for behavior under cancellation; choose unit tests for control-flow correctness.
- Operational note: add CI gates that require tests for continuation-based adapters and run tests under Main Thread Checker.

### Runtime observability
Add structured logs and lightweight identifiers to correlate Tasks to requests in your monitoring system. Temporarily increase logging for newly migrated adapters during rollout.

- Apple API/tool: Instruments (Allocations, Time Profiler), Main Thread Checker
- When to add observability: instrument adapters in the first rollout waves so you can quickly detect changes in latency, error rates, or resource usage.
- Operational note: monitor latency, error rate, cancellation propagation, and task counts. Roll back or gate changes if signals worsen.

## 5. TRADEOFFS, COMMON PITFALLS, AND OPERATIONAL CHECKLIST

### Tradeoffs and pitfalls
- Migration improves readability and provides explicit cancellation semantics, but increases coupling to the Swift concurrency runtime.
- Converting everything at once increases risk and makes rollbacks harder.
- Common pitfalls: using withUnsafeContinuation unsafely, not propagating cancellation, and overlooking Objective‑C consumers.

- When to migrate UI: consider delaying UI-layer conversions until service-layer adapters are stable and well-observed.
- Operational note: verify crash reports and telemetry after migration; async code may require different instrumentation patterns.

### Practical pre-release checklist
- Inventory callback origins (URLSession, DispatchQueue, NotificationCenter, third-party SDKs).
- Add async overloads in extensions; keep legacy callbacks during migration.
- Use withCheckedThrowingContinuation inside adapters; add debug assertions for double resume.
- Ensure cancellation calls URLSessionTask.cancel() or Operation.cancel().
- Write XCTest unit tests + URLProtocol stubs for success, failure, and cancellation.
- Run Instruments and Main Thread Checker; validate task and resource counts.
- Gate rollout with feature flags and monitor error-rate and latency.

## Closing Takeaway

Treat structured concurrency as an interface-level modernization: wrap and test service boundaries, propagate cancellation into system APIs, and gate rollouts with telemetry. Small, observable adapters let you adopt async/await incrementally and reduce the risk of destabilizing releases. If your codebase has heavy Objective‑C interop or third‑party constraints, run a scoped spike to validate the most critical adapters before a wider rollout.

## Swift/SwiftUI Code Example

_No validated code snippet was generated this run._

## References

- No verified external references were available this run.
