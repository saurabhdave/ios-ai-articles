Crashing previews, mis-scoped rollouts, and list cells that re-render on every scroll often point to the same root cause: unscoped dependencies. Treat the SwiftUI environment as a typed policy layer and keep ownership/mutation out of it.

- Centralize cross-cutting concerns in `EnvironmentValues` (time, `Logger`, formatting, flags) and set them at a composition root via `.environment(_:_:)`.
- Define custom `EnvironmentKey`s with safe defaults (e.g., deterministic clock, no-op logging, disabled flags) so previews/tests are predictable.
- Prefer read-only façades over mutable models in

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
