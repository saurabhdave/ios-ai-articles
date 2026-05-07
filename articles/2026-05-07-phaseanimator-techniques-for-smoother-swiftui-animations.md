# PhaseAnimator Techniques for Smoother SwiftUI Animations

Flicker, multi-render storms, and mid-animation orphaned views are common when sequential motion is driven by scattered `withAnimation` calls and shared observable state. Phase-based coordination centralizes sequencing, reduces jitter under load, and makes rollouts easier to reason about—provided you design ownership, interruption handling, and observability first.

## Why This Matters For iOS Teams
Designers expect choreographed, multi-stage motion: entrance → emphasis → settle. Naive use of `withAnimation` scatters timing decisions across the view tree and amplifies re-renders when many views observe the same model. In practice this surfaces as visible flicker or increased CPU work during high-frequency updates.

Centralizing sequencing into a single coordinator reduces regression surface area at the cost of added coordination complexity. Test phase boundaries, cancellation, and rollout behavior before enabling wide deployment.

> Centralize phase ownership; explicit interruption semantics turn flakey motion into predictable, testable state transitions.

## 1. PhaseAnimator Fundamentals
### Phase Coordination As A Pattern
Anti-pattern → preferred: scattering `withAnimation` calls in children makes ordering non-deterministic. When multiple views must advance through named stages, use a single coordinator that owns the phase and exposes a read-only view to children via `@Published` state on an `ObservableObject`. Choose a simple `withAnimation` approach when you only need single-property fades; choose a coordinator when ordering or multi-view choreography matters.

Testing and rollout: ensure the coordinator's ownership is clear and not shared across independent hierarchies to avoid duplicate reactions. Add unit tests that confirm phase transitions mutate only the coordinator's state and UI tests that assert final visual states per phase.

```swift
final class AnimationCoordinator: ObservableObject {
  @Published private(set) var phase: Int = 0
  func nextPhase() { phase += 1 }
}
```

Use `@StateObject` in views to own the coordinator instance, or inject a shared coordinator when a single authority is required for the whole flow. Validate deallocation in teardown tests to avoid retained coordinators causing post-release memory issues.

## 2. Timing, Easing, And Interruption Handling
### Assign Intent Per Phase
Anti-pattern → preferred: wrapping a flow with a single global `Animation` flattens motion intent. Assign a distinct `Animation` per phase (for example, an interactive spring for entrance and an `easeOut` for emphasis). Choose `Transaction` with `disablesAnimations` when you need snapshot semantics (snapbacks on cancellation); choose animated transitions when you want graceful fallback.

Make interruption handling explicit: decide whether a canceled interaction should animate to a fallback phase or snap immediately, and write tests that simulate mid-flight cancellations. Use `Transaction` during cancellation paths to suppress implicit animations when you want immediate visual state changes.

## 3. Composition Patterns And Interoperability
### UIKit Interop With Phase State
Anti-pattern → preferred: letting SwiftUI phase state and `UIViewPropertyAnimator` instances run independently can desynchronize motion. Map phases to a UIKit adapter that starts, pauses, or reverses `UIViewPropertyAnimator` instances based on the coordinator's phase. Choose `UIViewPropertyAnimator` when you need precise interruptibility; choose native SwiftUI `Animation` when you prefer SwiftUI to remain authoritative.

Gate cross-framework transitions behind a feature flag during rollout and validate on representative hardware to detect layout thrash. Observe coordinator phase changes and ensure the adapter follows state instead of attempting to own it, so rollback to a SwiftUI-only path remains simple.

```swift
final class UIKitAdapter {
  private var animator: UIViewPropertyAnimator?
  func sync(phase: Int) {
    switch phase {
    case 0: animator = UIViewPropertyAnimator(duration: 0.3, curve: .easeIn) { /* layer updates */ }; animator?.startAnimation()
    case 1: animator?.pauseAnimation(); animator?.isReversed = false
    default: animator?.stopAnimation(true); animator = nil
    }
  }
}
```

## 4. Performance And Resource Safety
### Profiling Phase Graphs
Avoid adding micro-phases without profiling; excessive micro-phases increase CPU work and layer counts. Choose to collapse adjacent micro-phases when Instruments (`Time Profiler`, `Allocations`) show frame drops or high CPU usage; choose finer phases when designer intent demands discrete, observable steps.

Audit capture lists in animation closures to avoid retain cycles and consider annotating coordinator state with `@MainActor` or placing it behind an actor if mutations may come from async contexts. Confirm coordinator and adapter instances are deallocated on teardown via unit or UI tests to prevent post-release memory regressions.

Testing guidance: include performance gates in your CI that run a representative scenario under `Time Profiler` to detect regressions early.

## Tradeoffs And Pitfalls
Deterministic phases improve predictability but add coordination overhead and verbosity. Over-sequencing can hurt responsiveness: each extra micro-phase increases the chance of interruption mismatch under load. A frequent mistake is moving phase logic into widely shared observable models, which produces redundant triggers and re-render storms.

Gate phased animation behind a feature flag and stage rollouts across a range of devices so you can rollback quickly if regressions appear. Document phase boundaries in your style guide to reduce accidental coupling.

## Validation And Observability
### Three Complementary Axes
Include automated correctness checks, local profiling, and release telemetry before rollout. Use `XCTest` UI tests with async expectations that assert final visual state and simulate cancellations. Run Instruments on device using `Time Profiler` and `Allocations` to detect CPU hotspots and retention during phase transitions.

Emit `OSSignposter` signposts for phase start/stop to measure wall-clock durations and correlate spikes in field telemetry; keep signposts behind a feature flag to limit noise. Use structured logging for phase outcomes (success, canceled, fallback) to aid diagnostics. Instrument key flows and run them as part of preflight validation on representative hardware.

## Practical Checklist
- [ ] Introduce phase-coordination wrappers for complex view groups and document phase boundaries in the team style guide.
- [ ] Ensure a single coordinator owns phase state; children consume a read-only derived view.
- [ ] Add `XCTest` UI tests asserting final visual state per phase and synthetic interruption scenarios.
- [ ] Instrument phase start/stop with `OSSignposter` and log key events via structured logging behind a feature flag.
- [ ] Profile representative flows on device with Instruments (`Time Profiler`, `Allocations`) and reduce layer count if FPS drops.
- [ ] Gate rollout with remote-config or a feature-flag to enable fast rollback on animation regressions.
- [ ] Audit closures and capture lists in animation blocks to prevent retain cycles; confirm coordinator deallocation.

## Closing Takeaway
Phase-based sequencing delivers more deterministic, testable motion when a single coordinator owns phase state and cancellation behavior is defined. Combine phase-specific `Animation` choices, a `UIViewPropertyAnimator` adapter where necessary, and release-ready signposting to surface regressions in the field. Ship phased animations incrementally behind a feature flag and validate with UI tests and device profiling so designer intent is met without increasing rollout risk.

## Swift/SwiftUI Code Example

```swift
import SwiftUI
import Observation

enum MotionPhase: Int {
    case idle, entrance, emphasis, settle
}

@MainActor @Observable
final class PhaseAnimator {
    var currentPhase: MotionPhase = .idle
    private var runningTask: Task<Void, Never>?

    func runSequence() {
        runningTask?.cancel()
        runningTask = Task { [weak self] in
            guard let self else { return }
            await transition(.entrance, duration: 0.25)
            try? await Task.sleep(nanoseconds: 200_000_000)
            if Task.isCancelled { return }
            await transition(.emphasis, duration: 0.35)
            try? await Task.sleep(nanoseconds: 300_000_000)
            if Task.isCancelled { return }
            await transition(.settle, duration: 0.28)
            try? await Task.sleep(nanoseconds: 150_000_000)
            if Task.isCancelled { return }
            await transition(.idle, duration: 0.0)
            runningTask = nil
        }
    }

    private func transition(_ phase: MotionPhase, duration: Double) async {
        await MainActor.run {
            withAnimation(.interactiveSpring(response: duration)) {
                currentPhase = phase
            }
        }
    }

    func cancel() {
        runningTask?.cancel()
        runningTask = nil
        currentPhase = .idle
    }
}

struct PhaseDemoView: View {
    @State private var animator = PhaseAnimator()

    var body: some View {
        VStack(spacing: 20) {
            ZStack {
                Circle()
                    .fill(.blue)
                    .frame(width: size(for: animator.currentPhase), height: size(for: animator.currentPhase))
                    .opacity(opacity(for: animator.currentPhase))
                    .scaleEffect(scale(for: animator.currentPhase))
                    .animation(.default, value: animator.currentPhase)
                Text(label(for: animator.currentPhase))
                    .foregroundColor(.white).bold()
            }
            HStack {
                Button("Play") { animator.runSequence() }
                Button("Cancel") { animator.cancel() }
            }
        }
        .padding(30)
    }

    private func size(for phase: MotionPhase) -> CGFloat {
        switch phase {
        case .idle: return 60
        case .entrance: return 100
        case .emphasis: return 140
        case .settle: return 80
        }
    }
    private func scale(for phase: MotionPhase) -> CGFloat {
        switch phase {
        case .entrance: return 1.05
        case .emphasis: return 1.25
        case .settle, .idle: return 1.0
        }
    }
    private func opacity(for phase: MotionPhase) -> Double {
        switch phase {
        case .entrance: return 0.9
        case .emphasis: return 1.0
        case .settle, .idle: return 0.95
        }
    }
    private func label(for phase: MotionPhase) -> String {
        switch phase {
        case .idle: return "Idle"
        case .entrance: return "Entrance"
        case .emphasis: return "Emphasis"
        case .settle: return "Settle"
        }
    }
}
```

## References

- [View.body](https://developer.apple.com/documentation/swiftui/view/body-swift.property)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
