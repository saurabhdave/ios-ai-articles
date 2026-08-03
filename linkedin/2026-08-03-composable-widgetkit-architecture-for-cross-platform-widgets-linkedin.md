Stale Lock Screen entries and reload storms often trace back to implicit data flows and per-platform forks. Treat the widget extension as a product with explicit budgets, not a background view that “just updates.”

- Centralize rendering in a shared SwiftUI module and gate by `WidgetFamily`, not by separate projects. One source of truth; platform shims only where density or contrast diverge.
- Prefer `AppIntentConfiguration` with an `AppIntentTimelineProvider` so timelines can be scoped to user parameters and async fetching stays

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
