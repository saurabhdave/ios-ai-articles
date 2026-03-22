Converting globals to explicit DI often surfaces production-only failures: blank screens, duplicated network calls, or stale `ObservableObject` state that don't crash but lengthen incident time.

Wire services at the `@main` App or per `Scene` so lifetimes are auditable and testable; avoid creating heavyweight clients inside view initializers.

Use constructor injection for replaceability in tests and staged rollouts; use `@StateObject`/`@ObservedObject` when multiple views must observe a shared model.

Gate new implementations with feature flags and provide a fallback or circuit-breaker so the UX can survive a degraded injected service.

Trace DI and network boundaries with `OSSignposter` and `OSLog`, and validate replacement paths with `XCTest` async tests.

Choose constructor injection when you need a narrow blast radius and reversible rollouts — accept modest constructor boilerplate for safer rollbacks.

Who on your team owns DI rollouts and rollback playbooks today? Interested in comparing patterns and failure modes.

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
