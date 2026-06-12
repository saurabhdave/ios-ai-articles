Renaming or reordering menus can silently break shortcuts, AppleScript/AppleEvent hooks, and assistive discovery — treat a menu redesign as a migration, not a string swap.

- Inventory command identity: map each menu item to a stable identifier (for example, `NSUserActivity.activityType` or an internal enum) instead of relying solely on visible title text.
- Preserve compatibility: consider shims that map legacy AppleEvent selectors and activity types to new handlers for a transition window; log invocations with `os_log` for telemetry.
- Test visibility: add accessibility narration checks, automation smoke tests, and end-to-end `XCTest` UI scenarios that select items via accessibility identifiers.
- Observe and gate: instrument routing with signposts (e.g., `os_signpost`) and gate rollout with feature flags tied to support and latency signals.

Tradeoff: keep compatibility shims while customers rely on automation; remove them only after telemetry and documentation support the cutover.

Which command paths in your app are automation‑critical and deserve a compatibility window? Share one example and how you’d detect when it’s safe to remove shims.

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
