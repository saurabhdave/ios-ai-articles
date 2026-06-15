On visionOS, navigation issues often show up at state boundaries—not just buttons. When 2D windows, 3D spaces, and restoration drift, back gestures and focus can feel inconsistent. Treat routes as data and aim for deterministic transitions.

- One window, one container: use `NavigationStack` for shorter linear flows; prefer `NavigationSplitView` when context should persist across activations. Avoid nesting stacks.
- Drive from a single `Router` with a `Codable` `Route` and a bound `NavigationPath`. Use `navigationDestination(for:)` over scattered booleans.
- Serialize immersive transitions. Queue `openImmersiveSpace` / `dismissImmersiveSpace` so only one space action runs before a route push.
- Persist per-window paths with `@SceneStorage`. Validate deep links and restore only safe routes; redirect to a 2D fallback when prerequisites may be missing.
- Gate gestures on scene activity

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
