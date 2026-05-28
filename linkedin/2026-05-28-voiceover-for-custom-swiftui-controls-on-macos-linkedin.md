A SwiftUI canvas that looks perfect but VoiceOver only reads “group” usually means accessibility semantics or notifications were never made explicit — pixels aren’t the whole contract.

- Map roles explicitly: prefer `accessibilityLabel` / `accessibilityValue` for simple items; when you need deterministic semantics or hit-testing, consider a small `NSViewRepresentable` bridge and set `isAccessibilityElement` and `accessibilityRole`.
- Expose a single, well-scoped accessibility element rather than hiding many subviews with `accessibilityHidden(true)` whenever possible.
- For dynamic updates, debounce and post the appropriate AppKit accessibility notifications so assistive tech gets stable announcements instead of floods.
- Test with assertions for role/trait presence and `accessibilityFocused` transitions — and validate behavior with VoiceOver on real hardware, not only the simulator.

Tradeoff: prefer pure SwiftUI for lower maintenance, but use a minimal AppKit bridge when you need deterministic accessibility or hit-testing behavior.

What tradeoff has surprised your team most when adding VoiceOver support to dynamic SwiftUI canvases? Let’s compare approaches and test strategies.

#SwiftUI #macOS #Accessibility #AppKit #iOS
