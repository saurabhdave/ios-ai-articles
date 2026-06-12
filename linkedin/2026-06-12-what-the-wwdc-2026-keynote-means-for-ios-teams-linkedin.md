Structured concurrency and observability are now platform-level architectural concerns — get cancellation and state ownership wrong and you may end up with leaked child tasks, held connections, and UI that doesn't match after rapid navigation.

Practical steps to start this quarter:

- Pilot one network flow with `TaskGroup` and add XCTest async tests that assert cancellation behavior before a broader rollout.
- Define `@MainActor` boundaries for UI-mutating state and enable runtime/CI checks that fail on violations.
- Add schema/version keys for on-disk caches and gate background-sync migrations behind feature flags or staged releases.
- Instrument hot paths with `OSSignposter` and correlate signposts with aggregated telemetry from `MetricKit` and structured `os_log` for faster diagnosis.

Tradeoff: use `Task.detached` only when work must intentionally outlive the UI; otherwise prefer scoped `TaskGroup` or structured tasks.

Which single flow will your team convert and instrument first this quarter?

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
