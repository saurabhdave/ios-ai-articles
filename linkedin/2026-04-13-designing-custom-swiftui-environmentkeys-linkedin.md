Implicit environment values can hide costly dependencies — multiple ancestors injecting the same observable can lead to unexpected re-renders and harder debugging.

Practical guidance when designing custom `EnvironmentKey`s:

- Prefer `EnvironmentKey` for cross-cutting, read-only context that many views need; choose explicit initializer parameters when a component must own lifecycle or teardown.
- Give `EnvironmentKey.defaultValue` an immutable, conservative fallback (struct/enum). Avoid mutable singletons or silently returning `nil`.
- Provide one clear injection point per navigation flow and a small view modifier to document scope; instrument provisioning with structured logs or signposts to aid tracing.
- Add migration shims when renaming keys so old and new paths can coexist; unit-test both injected and default behaviors.

In short: choose explicit parameters when a view owns lifecycle; choose `EnvironmentKey` for wide, read-only context.

Do you track environment provisioning with traces/signposts, or rely on unit tests to catch missing injections? Which approach has reduced debugging time for you?

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
