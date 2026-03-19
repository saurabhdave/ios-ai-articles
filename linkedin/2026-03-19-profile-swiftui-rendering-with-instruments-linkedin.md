Rendering regressions often surface in user reports long before engineers see them. In SwiftUI, the work that costs you can be hidden in view-diff churn, image decoding, or excess compositing.

- Profile representative lower-end devices with `Instruments` (`Time Profiler`, `Allocations`, `Core Animation`) before changing code paths.
- Add `os_signpost` around image loads, layout passes and custom draw to map high-level UI actions to traces you can act on.
- Reduce broadcast updates: prefer view-local `@State` or split hot `@Published` properties so diffs stay scoped and allocations are less likely to spike.
- Measure layout vs draw tradeoffs: only replace many composited subviews after comparing CPU cost versus Core Animation overhead.

Prefer system layer-backed compositing when it reduces CPU under realistic load; prefer consolidated drawing when lowering layer count measurably cuts frame cost.

Validate fixes in CI with targeted `XCTest` timing assertions and run post-release canaries or telemetry checks before a broad rollout.

Who on your team owns the signpost-to-trace mapping? I can pair with them to add targeted `os_signpost` spans for a hotspot you’re tracking.

#SwiftUI #iOSDev #Performance #Instruments #iOS
