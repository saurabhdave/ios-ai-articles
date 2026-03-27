A tiny change to `body` or to state ownership can raise per-frame CPU on lower-end devices and turn a calm rollout into an urgent rollback.

Profile on representative physical devices (include lower-end models) with `Time Profiler`, `Core Animation`, and `Allocations` to surface CPU, compositing, and churn hotspots.

Use `OSSignposter` to mark coarse phases (for example: decode, layout, render) and add finer signposts only in narrow canaries so you can correlate trace phases without inflating overhead.

Move heavy per-frame work out of `body`: precompute or decode images off the main thread and inject a ready-to-draw `CGImage` into views when possible.

Gate instrumentation and ownership changes behind feature flags, and attach representative `Instruments` traces to bug reports to aid reproducibility.

Choose explicit state ownership when you need predictable lifetimes and narrower render boundaries; prefer view-local `@State` for tiny, tightly scoped data.

Combine `OSSignposter`, `Instruments`, and CI- or `XCTest`-gated performance checks to make a repeatable trace → instrument → validate loop.

Have you used signposts in a canary to catch a render regression before rollout? Share one concrete lesson and what you changed as a result.

#SwiftUI #iOSDev #Performance #MobilePlatform #iOS
