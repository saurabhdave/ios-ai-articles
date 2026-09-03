# Designing Core Haptics for macOS Apps

Your Mac build can feel perfect on a Force Touch trackpad and completely silent on a desktop with a third‑party mouse. The same gesture that confirms intent on a MacBook Pro becomes a non-event on a Studio behind a KVM. If you don’t gate capabilities, warm the engine, and design fallbacks as product decisions, you’ll ship “random” failures that your CI will never catch.

> If the fallback path isn’t treated as a first‑class product decision, it becomes your primary failure mode in production.

*All code in this article targets macOS 26+ and Swift 6.2 unless noted otherwise.*

## Why This Matters

Teams are porting iPhone interaction patterns to macOS, where input hardware varies widely and can change at runtime. Users notice when a “success” haptic fires on one desk and disappears on another. Inconsistent feedback drives perception drift and vague bug reports that stall triage.

Core Haptics on macOS is powerful, but the engine is stateful and can be interrupted. If you don’t implement reset and stop handling, playback may fail after an audio system change. Enterprise environments also expect a user preference, accessibility alignment, and a clean no‑op when devices disconnect mid‑session.

## 1. Platform Capabilities And Fallback Strategy

### Ask The Hardware, Every Time

Detecting “MacBook” and assuming haptics exist is brittle. Lid closed, external display, KVM, or a disconnected trackpad can break that assumption. Always query CHHapticEngine.capabilitiesForHardware() and be prepared for the answer to change at runtime.

- When supportsHaptics is true, use Core Haptics.
- When Core Haptics isn’t available, use a coarse NSHapticFeedbackManager tap for acknowledgment cues.
- If nothing is appropriate for the context, no‑op rather than substituting sound.

```swift
import CoreHaptics
#if canImport(UIKit)
import UIKit
#endif
#if canImport(AppKit)
import AppKit
#endif

enum HapticDriver { case coreHaptics, appKit, uiKit, none }

@MainActor
struct HapticsCapability {
    static func currentDriver() -> HapticDriver {
        let caps = CHHapticEngine.capabilitiesForHardware()
        if caps.supportsHaptics { return .coreHaptics }
        #if canImport(UIKit)
        return .uiKit
        #elseif canImport(AppKit)
        return .appKit
        #else
        return .none
        #endif
    }
}

@MainActor
func fallbackTap() {
    #if canImport(UIKit)
    UIImpactFeedbackGenerator(style: .medium).impactOccurred()
    #elseif canImport(AppKit)
    NSHapticFeedbackManager.defaultPerformer.perform(.generic, performanceTime: .now)
    #else
    // No-op
    #endif
}```

Before → After:
- Before: cache supportsHaptics at launch and assume it forever.
- After: re-check capability right before every playback and branch accordingly.

Devices can appear and disappear during a session. Revalidate capability before each play and debounce repeated errors to avoid log floods.

## 2. Engine Lifecycle And Pattern Playback

### Keep One Warm Engine And Rebuild On Interruptions

Creating a new CHHapticEngine for every event adds latency and increases the chance of dropped cues under load. Maintain a single, durable engine per UI domain, warm it on first interaction, and enable isAutoShutdownEnabled so the system can reclaim resources after idle.

```swift
import UIKit
import CoreHaptics
import OSLog

@MainActor
final class HapticsEngineService {
    private let logger = Logger(subsystem: "com.example.app", category: "Haptics")
    private var engine: CHHapticEngine?
    private var players: [String: CHHapticAdvancedPatternPlayer] = [:]

    private func supportsHaptics() -> Bool {
        CHHapticEngine.capabilitiesForHardware().supportsHaptics
    }

    func prepare() {
        guard supportsHaptics() else { return }
        if engine == nil {
            engine = try? CHHapticEngine()
            engine?.isAutoShutdownEnabled = true
            engine?.resetHandler = { [weak self] in self?.rebuild() }
            engine?.stoppedHandler = { [weak self] reason in
                self?.logger.warning("Haptics stopped: \(reason.rawValue)")
                self?.rebuild()
            }
        }
        do {
            try engine?.start()
        } catch {
            logger.error("Failed to start haptics: \(String(describing: error))")
        }
    }

    func play(pattern named: String) {
        guard supportsHaptics() else { fallbackTap(); return }
        prepare()
        if players[named] == nil,
           let url = Bundle.main.url(forResource: named, withExtension: "ahap"),
           let pattern = try? CHHapticPattern(contentsOf: url),
           let engine = engine,
           let player = try? engine.makeAdvancedPlayer(with: pattern) {
            players[named] = player
        }
        do {
            try players[named]?.start(atTime: 0)
        } catch {
            logger.error("Playback failed for \(named): \(String(describing: error))")
            rebuild()
        }
    }

    private func rebuild() {
        players.removeAll()
        engine?.stop(completionHandler: { _ in })
        engine = nil
        prepare()
    }

    private func fallbackTap() {
        let generator = UIImpactFeedbackGenerator(style: .light)
        generator.prepare()
        generator.impactOccurred(intensity: 1.0)
    }
}```

Decision: warm one engine and reuse players; do not create engines per tap. Rebuild the engine and clear cached players in resetHandler and stoppedHandler.

Audio system changes and heavy load can interrupt playback. On any engine error or stop callback, rebuild instead of retrying blindly to improve recovery.

## 3. Authoring Reusable Haptics With AHAP

### Externalize Patterns And Add -mac Overrides

Hardcoding CHHapticEvent values locks you to a design that will change. Store patterns as .ahap files so design can iterate without touching code. Trackpads differ from phone taptic engines; what feels crisp on iPhone can feel subtle on a desktop trackpad.

```swift
import CoreHaptics

@MainActor
func loadPattern(named baseName: String) throws -> CHHapticPattern {
    let candidates = ["\(baseName)-mac", baseName]
    for name in candidates {
        if let url = Bundle.main.url(forResource: name, withExtension: "ahap") {
            return try CHHapticPattern(contentsOf: url)
        }
    }
    let event = CHHapticEvent(eventType: .hapticTransient, parameters: [], relativeTime: 0)
    return try CHHapticPattern(events: [event], parameters: [])
}
```

Use .ahap when:
- Product/design needs to own iteration without recompiles.
- You maintain platform-specific feel via filename variants like success-mac.ahap.

If a cue is too subtle, consider a brief .hapticContinuous with a ramped CHHapticParameterCurve for intensity to increase perception without feeling noisy.

Tightly packed sequences of transients and continuous segments can saturate on some devices, dropping later events. Merge into one continuous event with curves or add spacing.

## 4. UX Integration And Accessibility

### Respect App Focus And User Intent

Haptics should reinforce interaction, not background work. Provide a user preference, throttle frequency, and avoid firing while the app is inactive.

```swift
import UIKit
import CoreHaptics
import Foundation

@MainActor
final class HapticsEngineService {
    private var engine: CHHapticEngine?
    private let supportsHaptics = CHHapticEngine.capabilitiesForHardware().supportsHaptics

    func prepare() {
        guard supportsHaptics else { return }
        if engine == nil {
            let e = try? CHHapticEngine()
            e?.isAutoShutdownEnabled = true
            e?.stoppedHandler = { _ in }
            e?.resetHandler = { [weak self] in
                guard let self else { return }
                self.engine = try? CHHapticEngine()
                try? self.engine?.start()
            }
            engine = e
        }
        try? engine?.start()
    }

    func playTransient() {
        guard supportsHaptics else { return }
        prepare()
        let event = CHHapticEvent(
            eventType: .hapticTransient,
            parameters: [
                .init(parameterID: .hapticIntensity, value: 1.0),
                .init(parameterID: .hapticSharpness, value: 0.5)
            ],
            relativeTime: 0
        )
        guard let pattern = try? CHHapticPattern(events: [event], parameters: []),
              let engine = engine,
              let player = try? engine.makePlayer(with: pattern) else { return }
        try? player.start(atTime: 0)
    }
}```

Decision: only trigger cues from user interactions (selection, commit, error) and suppress when the app is not active. Avoid substituting audio for missing haptics; users often perceive it as noise.

Toggling the preference mid‑playback can race with teardown. Stop the engine or delay deallocation until idle.

## Tradeoffs And Pitfalls

- Capability variance is real. Validate on: a MacBook Pro built‑in trackpad, a Magic Trackpad over Bluetooth, and a desktop with only a mouse. Expect differences in amplitude and attack.
- A warmed engine reduces first‑tap latency but keeps a Core Audio graph resident. With isAutoShutdownEnabled, expect a slower first cue after long idle periods.
- .ahap reuse accelerates iteration, but parity with iPhone is unlikely. Maintain a small set of -mac variants instead of forcing iOS‑tuned values onto desktop hardware.
- Fallbacks are product design, not a tech afterthought. A single NSHapticFeedbackManager tap often beats sound substitutions that irritate power users.
- Apple has announced the conclusion of the Rosetta transition. macOS 27 will be the final release to support Rosetta on Apple silicon, and macOS 26.4 or later may notify users who launch apps that rely on Rosetta. Ship universal or Apple silicon native builds to ensure availability and avoid translation prompts.

## Validation And Observability

### Measure Cold Starts And Catch Field Failures

You will not validate haptic behavior on CI hardware. Split logic tests from device tests, instrument the runtime, and gate rollout.

- Use OSSignposter to bound cold start and first playback; compare warm vs. cold paths within your app’s context.
- Record structured events with os_log grouped by subsystem/category.
- Compare cold vs. warm paths in Instruments and confirm players aren’t leaked.
- Guard hardware‑dependent tests with XCTSkipIf and keep logic‑only tests for routing and preferences.
- Roll out behind a remote flag so you can disable Core Haptics quickly if failure rates increase.

```swift
import OSLog
import XCTest

let signposter = OSSignposter(subsystem: "com.example.app", category: "Haptics")

@MainActor
func measureStartAndPlay(_ service: HapticsEngineService) {
    let s1 = signposter.beginInterval("HapticsPrepare")
    service.prepare()
    signposter.endInterval("HapticsPrepare", s1)

    let s2 = signposter.beginInterval("HapticsFirstPlay")
    service.play(pattern: "success")
    signposter.endInterval("HapticsFirstPlay", s2)
}

final class HapticsTests: XCTestCase {
    func testCapabilityGates() throws {
        let caps = CHHapticEngine.capabilitiesForHardware()
        try XCTSkipIf(!caps.supportsHaptics, "No haptic hardware on this runner")
        XCTAssertTrue(caps.supportsHaptics)
    }
}
```

Log aggregation should count repeated errors rather than emit full stacks for each failure. Under high‑frequency interactions, per‑event logs can drown diagnostics you actually need; coalesce by error signature and surface rates over time windows.

## Practical Checklist

- [ ] Query CHHapticEngine.capabilitiesForHardware().supportsHaptics before each playback; route to Core Haptics, NSHapticFeedbackManager, or no‑op.
- [ ] Maintain a single CHHapticEngine, warm on first interaction, and enable isAutoShutdownEnabled.
- [ ] Implement resetHandler and stoppedHandler; clear cached players and rebuild on interruptions or errors.
- [ ] Store patterns as .ahap, support a -mac override, and validate feel on three representative hardware setups.
- [ ] Wrap engine start and first playback with OSSignposter; log structured failures and debounce repeats.
- [ ] Provide a user preference; suspend playback when the app is inactive; throttle high‑frequency cues.
- [ ] Gate device‑dependent tests with XCTSkipIf and keep CI green without haptic hardware.
- [ ] Ship a universal or Apple silicon native binary to align with Rosetta deprecation and avoid translation prompts.

## Closing Takeaway

On macOS, Core Haptics is a capability, not a guarantee. Treat the engine as a long‑lived, restartable subsystem, keep patterns external, and design fallbacks that still feel intentional. Measure cold starts and first‑tap latency so regressions show up in dashboards, not support tickets. Provide a user toggle and respect focus. With those guardrails, haptics become a reliable part of your interaction model instead of a novelty that fails at the worst moment.

## Swift/SwiftUI Code Example

_A code example for this topic is not included in this edition._

## References

- [Upcoming changes to Rosetta support for Intel-based macOS apps](https://developer.apple.com/news/?id=w5ngl9k2)
- [macOS 27.0 beta 8 (26A5425a)](https://developer.apple.com/news/releases/?id=08312026c)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
