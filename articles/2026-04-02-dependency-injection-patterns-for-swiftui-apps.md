# Dependency Injection Patterns for SwiftUI Apps

Converting global singletons into injectable services often surfaces as runtime failures: unexpected nil environment values in some view trees, duplicated observable owners that increase renders during scrolling, or cache and state mismatches after changing a service's lifetime. These failures may only appear under certain navigation paths or device profiles and can be time-consuming to diagnose if ownership is not explicit.

## Why This Matters For iOS Teams
Production SwiftUI apps are stateful systems with rollout constraints, telemetry, and concurrency considerations. Making dependency ownership explicit reduces the blast radius when you change behaviour, lets you canary safely, and makes regressions easier to trace with signposts and metrics. When a view can mutate a dependency, make that ownership visible in the constructor; otherwise you create implicit coupling that can surface under load or complex navigation.

> Make ownership explicit: if a view can mutate a dependency, show it in the constructor so lifecycle and mutation intent are clear.

## 1. Environment And View-Scoped Dependencies
### Use `Environment` For Lightweight UI Values
Choose `Environment` when the value is small and tied to a view tree; choose constructor injection when the dependency has an independent lifecycle or represents a service with resources. `Environment` excels for formatters, layout flags, or theme values that are cheap to copy and bound to `View` trees.

When migrating a formatter from a global to `Environment`, add tests that inject a controlled `EnvironmentValues` to assert formatting rules, and run a small rollout to validate routing paths that rely on the value. Watch for runtime failures such as missing `@Environment` values when views are created outside the expected hierarchy.

Example: lightweight formatter in the environment.
```swift
import Foundation
import SwiftUI

struct DateFormatterKey: EnvironmentKey {
  static let defaultValue: DateFormatter = {
    let f = DateFormatter()
    f.dateStyle = .short
    return f
  }()
}
extension EnvironmentValues {
  var shortDateFormatter: DateFormatter { self[DateFormatterKey.self] }
}

struct ContentView: View {
  @Environment(\.shortDateFormatter) var formatter
  var body: some View { Text(formatter.string(from: Date())) }
}
```

## 2. Constructor Injection And View Lifecycle Ownership
### Make The View The Owner When Lifecycle Should Match UI
Choose constructor injection when the model's lifecycle should match the `View` lifecycle; choose a higher-level scope or container when the instance should outlive the view. Creating and injecting `ObservableObject` view models in the view makes ownership explicit and avoids hidden singletons.

Use `@MainActor` on UI-facing mutable state and assert deallocation during navigation tests to avoid leaks. Replace production services with test doubles in unit tests to verify behavior and error handling. Validate that instances are deallocated when expected and that network or disk resources are released after navigation.

Example (constructor injection, actor-aware):
```swift
import Foundation
import Combine

@MainActor
final class ProfileViewModel: ObservableObject {
  private let profileService: ProfileServiceProtocol
  @Published var name: String = ""

  init(profileService: ProfileServiceProtocol) {
    self.profileService = profileService
  }

  func load() async {
    do {
      let profile = try await profileService.fetchProfile()
      name = profile.name
    } catch {
      name = "Unknown"
    }
  }
}

protocol ProfileServiceProtocol {
  func fetchProfile() async throws -> Profile
}
struct Profile { let name: String }
```

## 3. Service Containers And Resolver Patterns
### Prefer Lightweight Containers With Factories Over Global Registries
Choose a passed `AppContainer` when you need runtime swapping or late binding; choose a global registry only when unavoidable compatibility constraints exist. A small container that exposes factory closures keeps wiring explicit and makes it easier to test and replace dependencies per feature.

When a container's lifetime changes (for example, singleton to transient), add contract tests and a limited rollout to detect functional differences such as duplicated network requests or missing caches. Instrument service resolution with signposts so you can correlate resolver events with profiler samples and telemetry.

Example container:
```swift
import Foundation

struct AppContainer {
  let userServiceFactory: () -> UserServiceProtocol
  static let production = AppContainer(
    userServiceFactory: { UserService(session: .shared) }
  )
}

protocol UserServiceProtocol {
  func fetchUser(id: String) async throws -> User
}

actor UserService: UserServiceProtocol {
  let session: URLSession
  init(session: URLSession) { self.session = session }

  func fetchUser(id: String) async throws -> User {
    let (data, _) = try await session.data(from: URL(string: "https://api")!)
    // parse data into User — add proper parsing and error handling in real code
    return User(id: id)
  }
}

struct User { let id: String }
```

## 4. Scoping, Lifecycles And Concurrency Boundaries
### Scope Services To Limit Blast Radius
Choose view- or feature-scoped services to isolate lifecycles; choose app-scoped singletons only when a single source of truth is strictly required. Mark UI-facing mutable state with `@MainActor` or encapsulate shared mutable state in an `actor` to clarify concurrency boundaries.

Validate actor isolation and overlapping lifecycles during migration; mistakes at actor boundaries can cause stalls or contention that are detectable during profiling on device. Verify cancellation paths in async flows so tasks do not leak CPU or battery; include integration tests that assert behavior under concurrent access and cancellation.

## Tradeoffs And Pitfalls
- Strong typing and constructor injection improve testability but increase wiring and boilerplate during migration; prepare migration plans and tooling to reduce friction.
- Over-abstracting everything into protocols can hide intent and increase cognitive load for new engineers; prefer minimal, well-named interfaces that reflect async-safe contracts.
- Some third-party APIs or legacy SDKs effectively require global access; document those exceptions and confine global access to a single compatibility shim.
- Failure mode: multiple owners of the same `ObservableObject` instance across view trees can cause extra renders and higher CPU work during scroll-heavy workloads. Detect this through instrumentation and ownership audits.

## Validation And Observability
Use multiple signals to validate migrations and detect regressions. Unit and integration tests (including async expectations) should assert resolver contracts and async flows behave as expected. Instrument service resolution, network boundaries, and view model load events with signposts so you can correlate events with profiler samples.

Run on-device profiling with `Instruments` (Time Profiler, Allocations) to find UI-thread stalls and unexpected allocations. Collect structured logs and post-release telemetry to capture resolver failures and injection errors. Stage rollouts with feature flags and scoped canaries; correlate signposts, allocations, and telemetry before widening the rollout.

## Practical Checklist
- [ ] Inventory current global singletons and record usage sites and lifecycles.
- [ ] Define clear protocol interfaces for each service with async-safe contracts.
- [ ] Wire constructor injection for new view models and use `Environment` only for UI-scoped values.
- [ ] Add unit and integration tests for resolver wiring and injected mock behaviour.
- [ ] Instrument service resolution and async boundaries with signposts; collect structured logs and telemetry.
- [ ] Stage rollout with feature flags and scoped canaries; profile with `Instruments` on device.

## Closing Takeaway
Dependency injection in SwiftUI is about explicit ownership, measurable lifecycles, and clear concurrency boundaries. Start by inventorying globals, define small async-safe interfaces, and wire constructor injection where the view should own state. Use signposts, tests, and on-device profiling as guardrails so migrations reveal issues early and let you iterate with confidence.

## Swift/SwiftUI Code Example

```swift
import SwiftUI

private struct CompactLayoutKey: EnvironmentKey {
    static let defaultValue: Bool = false
}

extension EnvironmentValues {
    var isCompactLayout: Bool {
        get { self[CompactLayoutKey.self] }
        set { self[CompactLayoutKey.self] = newValue }
    }
}

extension View {
    func compactLayout(_ enabled: Bool) -> some View {
        environment(\.isCompactLayout, enabled)
    }
}

struct ListRowView: View {
    @Environment(\.isCompactLayout) private var isCompactLayout: Bool
    let title: String

    var body: some View {
        HStack {
            Text(title)
                .font(isCompactLayout ? .body.weight(.semibold) : .title3)
            Spacer()
            if !isCompactLayout {
                Image(systemName: "chevron.right")
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, isCompactLayout ? 6 : 12)
    }
}

struct ContentView: View {
    var body: some View {
        VStack(spacing: 12) {
            List(["One", "Two", "Three"], id: \.self) { item in
                ListRowView(title: item)
            }
        }
        // Inject lightweight UI flag at a known composition root
        .compactLayout(true)
    }
}
```

## References

- [View.body](https://developer.apple.com/documentation/swiftui/view/body-swift.property)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
