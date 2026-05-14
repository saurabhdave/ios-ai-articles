Migrating AppKit views to SwiftUI on macOS frequently surfaces runtime mismatches: responder-chain timing, lost first-responder, and scroll-time re-renders that can appear only on real hardware.

Inventory every `NSView`/`NSViewController` boundary before swapping in `NSHostingView`: record notifications, delegates, and assumptions about responder chain and event timing.

Centralize shared state into a single `ObservableObject` (or an actor for background work) and inject it into hosted views to reduce duplicated updates and excessive re-rendering.

Add lightweight signposts or logs around the hosting boundary and validate on real machines with profiling tools; simulator behavior can differ from device-level rendering and input timing.

Gate changes with feature flags and phased rollouts; collect structured logs for responder-chain and rendering events so you can correlate regressions to releases.

Choose `NSHostingView` when inputs are separable and state can be centralized; keep native `NSView` layers where precise `NSWindow` semantics or low-level event timing make a difference.

Pattern to try: pass a single model into the hosting boundary — `NSHostingView(rootView: FeedView(model: feedModel))`.

Want feedback on rollout strategies or to have me review a failing scroll-profile trace from your app? Share the trace or your rollout plan and I’ll suggest isolation points.

#SwiftUI #macOS #AppKit #Observability #iOS
