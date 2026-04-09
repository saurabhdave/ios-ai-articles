Encoded navigation state crossing package boundaries can cause runtime crashes when the host and a package decode routes differently.

Treat navigation as a value contract, not a view surface.

- Export small, `Codable`/`Hashable` route types and a thin router protocol. Let the app host own `NavigationStack` and `NavigationPath` so decoding happens where you control compatibility checks. 
- Add decoder fallbacks and a version/value discriminator on route payloads so unknown data maps to safe screens instead of failing decoding. 
- Inject routers via initializers or an `EnvironmentKey`; avoid global singletons that hide ownership and make lifetimes harder to reason about. 
- Instrument decode fallbacks and transition boundaries with `OSSignposter` and structured logs so you can correlate failures with telemetry and rollout behavior.

When multiple consumers exist, prefer staged migrations; reserve simultaneous swaps only when consumers can upgrade together.

How are you handling navigation contract compatibility across modular packages? Share a pattern, a short snippet, or a surprising tradeoff you've encountered.

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
