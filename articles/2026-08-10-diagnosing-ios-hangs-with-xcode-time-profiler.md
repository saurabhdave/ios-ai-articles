# Diagnosing iOS Hangs with Xcode Time Profiler

Hangs are the ugliest kind of failure in a shipped iOS app: no crash, no alert, just a frozen UI during a scroll, tap, or transition. The quickest way from “it feels stuck” to “this line is blocking the main thread” is a clean Instruments Time Profiler trace and a careful read of the main-thread stack. For example, a SwiftUI feed view can re-render more than expected if observation scopes are too broad—often fine in Simulator but worse on device under real I/O and scheduling.

> The most dependable signal for a hang is a trace that shows the main thread doing the wrong work for too long.

*All code in this article targets iOS 26+ and Swift 6.2 unless noted otherwise.*

## Why This Matters For iOS Teams

Production hangs hurt ratings and support. One blocking call on the main thread can undermine an otherwise solid release. Swift concurrency, SwiftUI, and friendly high-level APIs can hide expensive work under simple calls—like decoding or image processing on the main thread. This can show up via state mutations during `body` evaluation or callbacks that jump back to the main queue at the wrong time.

Treat profiling as a gate, not a suggestion. If a build can’t hold a smooth frame budget during key interactions on a device, it doesn’t ship.

## 1. Capture A Reproducible Trace With Time Profiler

### Use Time Profiler Intentionally

Open Instruments, choose Time Profiler, and enable “Record waiting threads.” That option helps when the app appears idle but is actually blocked on a wait. Reproduce the hang on a physical device, capture long enough to include the stall, then stop and save the trace.

When the UI is stuck and CPU might be busy or blocked, use Time Profiler. When you investigate memory churn, use Allocations. The Simulator’s scheduling and I/O often differ from devices; profile on device where caches, storage, and thermal behavior match reality.

Decision point:
- Prefer device traces for scroll, decoding, image work, and startup to capture real I/O and scheduling.
- Use Simulator only for quick iteration, not to close performance bugs.

Keep a repeatable repro script (steps, data, screen) alongside the trace so another engineer can verify the stall without guesswork.

### Symbolication Is Non-Negotiable

Sampling without symbols turns the call tree into guesswork. Ensure dSYMs are available for any build you profile and confirm symbolication before drawing conclusions.

Contrast:
- Naive: “We can’t reproduce locally; let’s read logs.”
- Correct: Reproduce on device, record with Time Profiler + waiting threads, verify symbols, then attribute.

## 2. Read Stacks And Attribute The Stall

### Start At The Main Thread

Filter the call tree to the main thread and expand to the top self-time frames. If you see synchronous I/O, decoding, image processing, or blocking waits, you’ve found a likely cause. Expand system frames until you reach your code—Core Graphics, ImageIO, or Foundation calls can obscure the origin.

When cross-queue waits exist, “Record waiting threads” can highlight a background callback that synchronously dispatches to the main queue while the main queue is waiting on that background queue—an easy path to deadlock. Favor async boundaries to avoid this.

### Replace Synchronous Boundaries

Treat any single unit of main-thread work that exceeds a frame budget as a defect. Move the heavy work off-main and reenter the UI intentionally via `@MainActor` or an actor boundary.

```swift
import Foundation

struct Post: Decodable { let id: Int; let title: String }

actor FeedStore {
  private(set) var posts: [Post] = []

  func update(with data: Data) async throws {
    // Off-main: decode on a background thread
    let decoded: [Post] = try await withCheckedThrowingContinuation { cont in
      DispatchQueue.global(qos: .userInitiated).async {
        do {
          let result = try JSONDecoder().decode([Post].self, from: data)
          cont.resume(returning: result)
        } catch {
          cont.resume(throwing: error)
        }
      }
    }
    // Back on the actor: state update is serialized and safe
    posts = decoded
  }
}
```

Before: decoding inside a `@MainActor` update shows long frames during scroll. After: decoding happens off-main and the main thread no longer carries that work during interaction.

Always correlate the fixed trace to the same repro. If top self-time simply moved elsewhere on the main thread, you hid the problem rather than fixing it.

## 3. Move Work Off The Main Thread Safely

### Use Background Queues Deliberately, Return On `MainActor`

Parsing, decoding, and image resizing belong off-main. UI state changes and view updates belong on the `@MainActor`. Keep this boundary explicit and consistent.

```swift
import Foundation
import UIKit
import Observation
import ImageIO
import MobileCoreServices

@MainActor
@Observable
final class ImageCellState {
  var image: UIImage? = nil
}

func loadThumbnail(url: URL, state: ImageCellState) {
  let qos = DispatchQoS.QoSClass.userInitiated
  DispatchQueue.global(qos: qos).async {
    guard
      let src = CGImageSourceCreateWithURL(url as CFURL, nil),
      let cgThumb = CGImageSourceCreateThumbnailAtIndex(
        src, 0,
        [kCGImageSourceCreateThumbnailFromImageAlways: true,
         kCGImageSourceThumbnailMaxPixelSize: 160] as CFDictionary
      )
    else { return }

    let result = UIImage(cgImage: cgThumb)
    Task { @MainActor in
      state.image = result
    }
  }
}
```

Decision point:
- Use `.userInitiated` QoS for work that immediately affects what’s on-screen; use lower priorities for prefetching or background preparation.
- Prefer batching related work (e.g., decode a page) over spinning up many tiny tasks to reduce overhead.
- Keep heavy computations and blocking I/O off-main; hop back to the main actor only to apply UI-visible state.

Avoid shared mutable state across queues. Use actor isolation for caches or encapsulate mutation behind `@MainActor` to prevent flicker and races.

## 4. Validate The Fix With Targeted Evidence

### Mark Hotspots With `OSSignposter`

Broad logging is noise; signposts give structure inside a trace. Bracket suspicious regions, re-run Time Profiler, and correlate labeled intervals with main-thread spikes.

```swift
import Foundation
import os

struct Post: Codable {}

let signposter = OSSignposter(subsystem: "com.acme.app", category: "performance")

func decodePosts(_ data: Data) throws -> [Post] {
  let state = signposter.beginInterval("decode.posts")
  defer { signposter.endInterval("decode.posts", state) }
  return try JSONDecoder().decode([Post].self, from: data)
}```

Decision point:
- Use `OSSignposter` for timing and boundaries you’ll inspect in Instruments.
- Keep general `os_log` for lightweight breadcrumbs, not for profiling.

Add signposts only where you need attribution; excessive intervals can dilute signal and add overhead.

## 5. Production Hardening And Rollout Gates

### Make Release Decisions On Traces, Not Hope

Compare like-for-like traces across builds for cold start, first scroll, and search typing. Use structured logs to annotate user actions so you can align spikes with behavior. Ship only when the main-thread profile for these flows is stable and within budget on physical hardware.

Decision point:
- Prefer device profiling over Simulator to capture real I/O and scheduling.
- Gate promotion when new code adds synchronous I/O or decoding reachable from the main thread, or when symbolication for the candidate build is incomplete.

Keep a checklist-driven go/no-go review with named traces attached to the release ticket. If the trace isn’t attached, it isn’t verified.

## Tradeoffs And Pitfalls

- Over-slicing work increases context switches and energy use. Prefer a small number of well-scoped tasks to many micro-tasks.
- SwiftUI observation scopes can increase render counts. A widely scoped observable can trigger broad invalidations; prefer narrow scopes and pass values when possible.
- Cross-queue waits invite deadlocks. A background callback that synchronously dispatches to the main queue while the main queue waits on that background queue can hang the app. Use async boundaries and avoid cross-queue waits.
- Priority inversion can stall the UI. Enqueue heavy work at appropriate QoS if the UI is waiting; avoid blocking the main thread awaiting low-priority tasks.
- Simulator profiling can misrepresent device I/O and scheduling. Validate on physical devices, including cold-start conditions.

## Validation & Observability

- Instruments Time Profiler: Record on device with “Record waiting threads.” Inspect the main-thread call tree and expand system frames until you hit your code. Keep saved traces for regression comparison.
- XCTest Performance: Add tests that exercise decoding paths, thumbnail generation, and view-model updates with deterministic input. Use async expectations to ensure no main-thread stalls on critical flows.
- OSSignposter: Bracket decode, image processing, and layout boundaries. Use signposts to align Instruments intervals with code intent.
- MetricKit: Collect hang diagnostics and CPU metrics post-release for trend monitoring. Treat them as lagging indicators—use them to confirm field behavior, not to replace on-device profiling.
- os_log: Add low-volume, structured breadcrumbs at user-action boundaries (open feed, start scroll, tap search). This ties field symptoms to code paths without polluting performance.
- Rollout Gates: Block promotion if symbolication is incomplete, main-thread self-time spikes during core flows, or newly reachable synchronous I/O appears on the main thread.

## Practical Checklist

- [ ] Reproduce the hang on a physical device, record with Time Profiler and “Record waiting threads,” and save the trace.
- [ ] Verify symbolication for the profiled build before analyzing the call tree.
- [ ] Attribute the stall: expand the main-thread stack to your leaf frames and identify synchronous I/O, decoding, image work, or waits.
- [ ] Remove heavy work from `@MainActor` paths; run it on a background queue with explicit QoS and reenter UI via `@MainActor` or an actor.
- [ ] Add targeted `OSSignposter` intervals; re-profile to confirm time moved off the main thread.
- [ ] Add XCTest performance tests with device-realistic inputs and budgets.
- [ ] Audit SwiftUI observation scopes; avoid a single observable shared across multiple ancestors in scrolling hierarchies.
- [ ] Set rollout gates tied to traces; do not promote builds that regress main-thread time on core flows.

## Closing Takeaway

Time Profiler turns “the app feels frozen” into concrete stacks you can act on. The fix is usually straightforward: push heavy work off the main thread, make the hop explicit, and prove it with a trace. Validate on physical devices, not the Simulator. Keep observation scoped, avoid cross-queue waits, and align QoS with user intent. When traces become part of release gates, hangs move from mystery to routine engineering work.

## Swift/SwiftUI Code Example

```swift
import SwiftUI
import Foundation
import Observation
import OSLog

struct FeedItem: Identifiable, Decodable, Equatable {
    let id: Int
    let title: String
}

@MainActor
@Observable
final class FeedModel {
    var items: [FeedItem] = []
    private let signposter = OSSignposter(subsystem: "com.example.app", category: "Feed")
    private let logger = Logger(subsystem: "com.example.app", category: "Feed")

    func load() async {
        let name: StaticString = "FeedLoad"
        let state = signposter.beginInterval(name)
        defer { signposter.endInterval(name, state) }
        do {
            let newItems = try await Self.fetchAndDecodeOffMain()
            logger.log("AssignItems.count=\(newItems.count, privacy: .public)")
            items = newItems
        } catch {
            logger.error("LoadFailed. \(String(describing: error), privacy: .public)")
        }
    }

    nonisolated private static func fetchAndDecodeOffMain() async throws -> [FeedItem] {
        let url = URL(string: "https://example.com/feed.json")!
        let (data, _) = try await URLSession.shared.data(from: url)
        return try await Task.detached(priority: .userInitiated) {
            let d = JSONDecoder()
            d.keyDecodingStrategy = .convertFromSnakeCase
            return try d.decode([FeedItem].self, from: data)
        }.value
    }
}

struct FeedView: View {
    @State private var model = FeedModel()
    var body: some View {
        List(model.items) { item in
            Text(item.title).lineLimit(1)
        }
        .task { await model.load() }
    }
}
```

## References

- [Instruments Help](https://developer.apple.com/documentation/xcode/gathering-information-for-debugging)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
