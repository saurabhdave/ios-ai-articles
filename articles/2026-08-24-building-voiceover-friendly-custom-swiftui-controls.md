# Building VoiceOver-Friendly Custom SwiftUI Controls

Custom SwiftUI controls can look perfect yet behave poorly with VoiceOver: actions aren’t discoverable, labels don’t reflect state, or focus jumps unexpectedly. That leads to QA blockers and follow-up churn. This piece shows patterns to make custom controls narrate clearly, act predictably, and remain responsive during list scrolling and rapid focus changes.

*All code in this article targets iOS 26+ and Swift 6.2 unless noted otherwise.*

## Why This Matters
Accessibility regressions are release blockers. When you introduce a custom control, you also define its narration, its actions, and its focus model. SwiftUI’s accessibility model differs from UIKit’s and gaps often surface only during real VoiceOver navigation.

Performance also matters. Broad state changes can trigger unnecessary updates across your view tree. In practice, this can cause scroll stutter on list-heavy screens when focus moves quickly.

> Treat accessibility as part of the control’s public API, not a bolt-on to its children.

## 1. Model The Control As One Accessible Element
### Wrap And Combine
Exposing each subview — icon, title, chevron, and badge — as separate accessible elements is noisy and brittle. Prefer a wrapper with `accessibilityElement(children: .combine)` and set `accessibilityLabel`, `accessibilityValue`, and traits like `.isButton` and `.isSelected` on the container.

```swift
import SwiftUI

@Observable
@MainActor
final class ToggleTagModel {
    var isOn: Bool = false
    var label: String = "Notifications"
}

struct ToggleTag: View {
    var model: ToggleTagModel
    let action: () -> Void

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: model.isOn ? "bell.fill" : "bell.slash")
            Text(model.label)
            Spacer()
            Image(systemName: "chevron.right")
                .opacity(0.4)
        }
        .padding(12)
        .background(model.isOn ? Color.blue.opacity(0.15) : Color.gray.opacity(0.12))
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .contentShape(Rectangle()) // full-row hit target
        .onTapGesture { action() }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(model.label)
        .accessibilityValue(model.isOn ? "On" : "Off")
        .accessibilityAddTraits(model.isOn ? [.isButton, .isSelected] : [.isButton])
    }
}
```

### Decision
When the control is semantically a single unit, use `.combine`. If a subview is independently actionable or needs a distinct rotor target, expose separate elements.

### Operational Note
Keep traits on the wrapper. Splitting traits between children and parent can lead to mismatched narration across releases and flakey tests that assert `label`/`value` strings.

## 2. Encode State And Intent With Hints And Actions
### Map Non-Standard Gestures
Custom gestures like `DragGesture` or manual long-presses won’t be discoverable to VoiceOver unless you provide accessibility actions. Use `accessibilityAdjustableAction` for increment/decrement semantics and named actions for custom operations. Keep `accessibilityValue` in sync with the visible state.

```swift
import SwiftUI

struct RatingControl: View {
    @State private var rating: Int = 0
    let max = 5

    var body: some View {
        HStack {
            ForEach(1...max, id: \.self) { i in
                Image(systemName: i <= rating ? "star.fill" : "star")
                    .onTapGesture { rating = i }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Rating")
        .accessibilityValue("\(rating) of \(max)")
        .accessibilityHint("Adjust with swipe up or down")
        .accessibilityAdjustableAction { direction in
            switch direction {
            case .increment:
                if rating < max { rating += 1 }
            case .decrement:
                if rating > 0 { rating -= 1 }
            @unknown default:
                break
            }
        }
    }
}
```

### Decision
When your control conceptually behaves like a `Stepper`, `Toggle`, or `Button`, map to built-in semantics (activation or adjustable). If the behavior doesn’t match system patterns, provide a clearly named custom action.

### Operational Note
Update values on the main actor so VoiceOver reads fresh state. If state changes are scheduled on background tasks, narration may lag under load. Keep `accessibilityValue` small, localizable, and stable.

## 3. Control Focus, Order, And Hit Targets
### Match Visual Scan Order
Your focus order should reflect how a sighted user scans the UI. Use `accessibilitySortPriority(_:)` to guide reading order and hide ornaments using `accessibilityHidden(true)`.

```swift
import SwiftUI

struct ProfileHeader: View {
    let name: String
    let subtitle: String

    var body: some View {
        HStack {
            Image(systemName: "person.crop.circle.fill")
                .font(.system(size: 44))
                .accessibilityHidden(true)

            VStack(alignment: .leading) {
                Text(name)
                    .accessibilitySortPriority(2)
                Text(subtitle)
                    .foregroundStyle(.secondary)
                    .accessibilitySortPriority(1)
            }
        }
        .padding()
    }
}
```

### Decision
When the view tree order doesn’t match reading order (e.g., overlays, ZStacks, or conditionally inserted views), set explicit priorities. When your layout is a simple top-to-bottom stack, rely on defaults.

### Operational Note
A misplaced `accessibilityHidden(true)` on a container hides entire subtrees and can trap focus. Keep activation points inside view bounds when using `accessibilityActivationPoint(_:)`, especially near screen edges on compact devices.

## 4. Announcements, Rotors, And Scroll Semantics
### Announce Meaningful Async Outcomes
When background work completes and changes the user’s task state, post an announcement with `UIAccessibility.post(notification: .announcement, argument: ...)`.

```swift
import UIKit

enum A11y {
    static func announce(_ message: String) {
        UIAccessibility.post(notification: .announcement, argument: message)
    }
}
```

Use concise, localized messages and prefer a single source of truth to avoid duplicates from both network completion and UI transitions.

### Use Rotors Where They Unlock Navigation
Custom rotors can make dense UIs efficient (e.g., jump among unread items). Keep rotor entries stable and localized, and test the fallback behavior when a collection is empty.

### Map Paged Content To Familiar Operations
For carousels and pagers, expose predictable next/previous operations so VoiceOver users can move between pages with standard gestures. For example, provide adjustable or clearly named actions that reflect page changes.

### Operational Note
Throttle announcements per screen. Over-announcing interrupts ongoing reading and forces VoiceOver to restart utterances, which slows navigation on busy screens. Log and deduplicate.

## 5. Performance And State Isolation Under VoiceOver
### Combine To Reduce Focus Churn
Every focus move can trigger state reads and re-renders. Combining subviews into one `accessibilityElement(children: .combine)` reduces churn and keeps narration atomic, especially in large lists.

```swift
import SwiftUI

@Observable
final class CellState {
    var title: String
    var isSelected: Bool = false

    init(title: String) { self.title = title }
}

struct ListCell: View {
    var state: CellState

    var body: some View {
        HStack {
            Text(state.title)
            Spacer()
            Image(systemName: state.isSelected ? "checkmark.circle.fill" : "circle")
        }
        .contentShape(Rectangle())
        .onTapGesture { state.isSelected.toggle() }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(state.title)
        .accessibilityValue(state.isSelected ? "Selected" : "Not selected")
        .accessibilityAddTraits(state.isSelected ? [.isButton, .isSelected] : [.isButton])
    }
}
```

### Decision
When lists update frequently, use isolated models per cell/control. Avoid capturing the same observable model instance across distant ancestors — it broadens invalidation scopes and can cause stutter when VoiceOver moves focus rapidly.

### Operational Note
Profile on device with VoiceOver enabled. Use Time Profiler to verify that state changes in one control don’t re-render unrelated siblings, and adjust model boundaries if they do.

## Tradeoffs And Pitfalls
- Over-grouping can hide legitimate sub-actions. If a control has two primary actions (e.g., open details vs. toggle favorite), either split into two tappables or expose multiple accessibility actions.
- Under-grouping increases focus stops and exhausts users in long lists. Group decorative content and surface a single tappable with combined `label`/`value`.
- Rotors and custom actions add localization and testing surface area. Budget time for per-locale verification and real-device passes.
- Focus and activation points near edges can mis-hit if the point leaves bounds. Keep `accessibilityActivationPoint(_:)` safely inside the control’s frame.
- Compatibility differences can occur across OS updates. Pin your minimum target realistically and validate narration and actions on physical devices representative of your user base.

## Validation And Observability
- XCUITest:
 - Query by `accessibilityIdentifier` and assert `label`/`value` for each custom control.
 - Verify `isHittable` after scrolling the element into view.
 - Use async expectations to wait for `accessibilityValue` changes after invoking adjustable or activation actions.
- Instruments:
 - Time Profiler on a physical device with VoiceOver enabled. Record scroll plus action flows and confirm updates don’t fan out to unrelated views.
 - Allocations to spot spikes from dynamic `Text`/`Image` work during state churn.
- Logging:
 - Use `OSSignposter` to bracket “announcement queued” to “announcement posted,” and add log metadata for control identifiers to correlate events and deduplicate.
- Post-Release:
 - Monitor `MetricKit` for animation hitches on screens with custom controls.
 - Gate new controls behind feature flags and enable incrementally to watch crash-free rates and support tickets before full rollout.

## Practical Checklist
- [ ] Wrap each custom control and set `accessibilityElement(children: .combine)`.
- [ ] Provide `accessibilityLabel`, `accessibilityValue`, and traits like `.isButton` and `.isSelected` on the wrapper.
- [ ] Map every custom gesture to `accessibilityAdjustableAction` or a named accessibility action, and keep `accessibilityValue` updated on the main actor.
- [ ] Align reading order with `accessibilitySortPriority(_:)` and hide decoration using `accessibilityHidden(true)`.
- [ ] Keep `accessibilityActivationPoint(_:)` inside bounds for small or irregular targets.
- [ ] Add stable `accessibilityIdentifier`s and XCUITests for labels, values, and hit-ability.
- [ ] Validate with Accessibility Inspector hit-testing and focus tracing before merge.
- [ ] Post `UIAccessibility` announcements for meaningful async outcomes; centralize and throttle to avoid duplicates.
- [ ] Profile on-device with Time Profiler; avoid sharing observable models across distant ancestors that cause redundant invalidations.

## Closing Takeaway
Start by modeling each custom control as a single accessible element with explicit labels, values, and traits. Map intent to standard actions so VoiceOver users can operate the UI without bespoke gestures. Keep focus order aligned with visual layout, hide decoration aggressively, and post announcements only when outcomes matter. Back these choices with tests, device profiling, and measured rollout. Once the fundamentals hold, add rotors and advanced behaviors where they clearly accelerate real tasks.

## Swift/SwiftUI Code Example

```swift
import SwiftUI

struct VOCombinedControl: View {
    @State private var isOn = false
    @State private var count = 3

    var body: some View {
        Button {
            isOn.toggle()
        } label: {
            HStack(spacing: 12) {
                Image(systemName: isOn ? "star.fill" : "star")
                    .foregroundStyle(isOn ? .yellow : .primary)
                Text("Favorites")
                Spacer(minLength: 8)
                Text("\(count)")
                    .monospacedDigit()
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Capsule().fill(.secondary.opacity(0.2)))
                Image(systemName: "chevron.right")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            .padding(.vertical, 8)
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Favorites")
        .accessibilityValue(isOn ? "On, \(count) items" : "Off, \(count) items")
        .accessibilityHint("Double-tap to toggle. Swipe up or down for more actions.")
        .accessibilityAddTraits(.isButton)
        .accessibilityAddTraits(isOn ? .isSelected : [])
        .accessibilityAction(named: isOn ? "Turn Off" : "Turn On") { isOn.toggle() }
        .accessibilityAction(named: "Increment Count") { count += 1 }
    }
}
```

## References

- [View.body](https://developer.apple.com/documentation/swiftui/view/body-swift.property)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
