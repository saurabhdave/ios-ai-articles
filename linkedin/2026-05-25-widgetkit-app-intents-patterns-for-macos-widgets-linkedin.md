Cross-process intent decoding can silently break widget updates — treat `AppIntent` parameters as a durable API.

- Prefer concrete types for intent parameters (`Int`, enums, `Date`). Use `String` only for truly free-form values. Add `XCTest` encode/decode cases that assert handler behavior when values are missing or malformed so regressions are caught during CI.
- Emit targeted timeline entries and call `WidgetCenter.shared.reloadTimelines(ofKind:)` selectively. Avoid blanket `reloadAllTimelines()` where a broad refresh could amplify load.
- Make open-from-widget paths idempotent and lazy-init heavy services; present a minimal UI if reconstructing state takes time.
- Instrument intent boundaries and timeline refreshes with `os_signpost` and structured `os_log` so decode failures and cold starts can be correlated with backend traces and user-visible errors.

Choose conservative timeline expirations when backend capacity or battery impact is a concern, and shorter expirations when freshness matters and servers can absorb the load. Use Instruments to validate cold-start impact and `AppIntent` behavior in end-to-end flows.

How have you handled cross-process intent decoding surprises during rollouts — which signals (logs, signposts, crash trends, telemetry) most often pushed you to roll back or gate?

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
