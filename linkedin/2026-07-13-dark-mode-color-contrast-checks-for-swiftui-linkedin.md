Dark mode regressions don’t show up as crashes—they ship as unreadable text on blurred cards and brand tints that vanish over images. Most teams compute contrast against a theoretical background, not the surface the GPU actually composites.

- Tokenize color roles, not RGBs. Use Asset Catalog roles (Any/Dark plus High Contrast) like Background, Surface, TextPrimary; call them via `Color("…")`.
- Make contrast a debug-time invariant. Add a `ViewModifier` that asserts using WCAG math on resolved `UIColor` pairs; log with `Logger` and honor `\.colorSchemeContrast`.
- Keep text at 1.0 opacity. Tune `Surface` opacity or layering; semi-transparent text over Material tends to undercut ratios.
- Validate the background you actually draw. For Material, put a solid role-backed fallback under it and compute against that; then spot-check with `Accessibility Inspector` on device.
- Preview fast, verify real flows. Some failures appear only with UIKit chrome—probe via `UIWindow.overrideUserInterfaceStyle(.dark)`.

Tradeoff: Choose solid-under-material when you need deterministic checks; prefer pure `.ultraThinMaterial` when you accept manual, device-first validation.

`SwiftUI`, `UIColor`, `Logger`, and `Accessibility Inspector` make this practical without shipping runtime overhead.

How are you encoding contrast thresholds in debug and catching violations before code review—asserts, snapshots, or both?

#SwiftUI #iOSDev #MobileAccessibility #UIKit #EngineeringLeadership
