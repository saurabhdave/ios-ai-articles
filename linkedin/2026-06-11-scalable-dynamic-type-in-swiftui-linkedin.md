A single shared observable can kill scroll performance: one mutation, many ancestors re-render, stuttery scrolling and layout shifts.

- Read `\(.sizeCategory)` as close to the view that renders text and prefer semantic `Font` for textual content. Use `@ScaledMetric` for non-font geometry (icons, gaps) so those values scale with Dynamic Type.
- Replace global mutable scale objects with immutable props or localized observables to reduce invalidation fan‑out. Precompute heavy layout work outside `View.body` when possible.
- On mixed `UIKit`/`SwiftUI` surfaces, consider wrapping `UIFontMetrics` in narrow adapters and snapshotting views at representative `DynamicTypeSize` values to check visual parity during migration.
- Profile on device with `Instruments` and correlate traces using `OSSignposter` to find expensive layout work and verify fixes during incremental rollouts.

Choose adapters for parity during migration; move to `Font` + `@ScaledMetric` once the surface area is small and verified.

How have you instrumented view invalidation to find fan‑out in large SwiftUI lists?

#SwiftUI #iOSDev #Accessibility #Performance #iOS
