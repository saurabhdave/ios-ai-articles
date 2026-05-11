# RealityKit Performance Tips for visionOS

Converting an ad-hoc RealityKit scene into a production-ready visionOS experience often fails at runtime: unexpected thermal rises, mid-session memory growth, or watchdog kills can appear only after wider testing. A few common patterns tend to cause these failures — deep transform hierarchies, unbounded concurrent asset loads, and non-deterministic GPU resource release — and you can mitigate them with small, testable changes.

## Why This Matters
Platforms with constrained thermal and power budgets make CPU, GPU, and memory behavior more visible during real user sessions. RealityKit scenes that behave in short development runs can show problems under longer sessions or when multiple apps are active. Teams migrating from UIKit/SceneKit to RealityKit benefit from more deterministic resource management, bounded concurrency for asset loads, and targeted observability so regressions are actionable. Without those controls, issues such as shader compilation spikes or bursts of concurrent asset loads can produce user-visible hitches or increased thermal and power usage in some scenarios.

## 1. Scene Graph And Entity Management
### Shallow Hierarchies For Frequently Updated Objects
Anti-pattern → Preferred: deep parent chains with per-frame transforms are costly. Replace nesting with flat containers and group animated children directly under a single Entity or AnchorEntity.

```swift
// Preferred: flat container for high-frequency updates
let anchor = AnchorEntity()
let container = Entity()
anchor.addChild(container)

let child = ModelEntity(mesh: .generateBox(size: 0.1))
container.addChild(child)

// Update transforms on `container` or direct children only
container.transform.translation.x += 0.01
```

When transforms change frequently, prefer shallower hierarchies. If you need inherited coordinate spaces for rare structural changes, deeper hierarchies are acceptable. Test this by creating a worst-case scene with many animated children on the target device and profile frame times with Instruments.

Include a unit or smoke test that renders a representative number of animated entities on-device and fails the run if frame time exceeds an acceptable threshold. This helps catch regressions in CI before rollout.

## 2. Rendering And Materials
### Use PhysicallyBasedMaterial With Baked Or Compressed Maps
Anti-pattern → Preferred: many layered HDR textures and frequent material swaps can increase shader permutations and GPU memory use. When appropriate, bake static lighting into texture maps (for example, base color and metallic/roughness) and use GPU-compressed texture formats.

When geometry is static, baking light contributions or static lighting into textures can reduce runtime shader complexity. Keep dynamic objects using appropriately sized runtime maps. Validate by swapping a material on many objects and observing shader compilation and GPU behavior in Instruments.

Maintain a build-time asset pipeline step that converts textures into GPU-friendly formats and emits a short report of top memory consumers. Add a visual smoke test that replaces materials on many objects and captures shader compile activity during the run.

## 3. Concurrency And Async Asset Loading
### Preload With Structured Concurrency And A Bounded Loader
Anti-pattern → Preferred: launching unbounded ModelEntity.load(contentsOf:) calls from the UI can saturate memory and I/O. Implement a bounded loader that limits concurrent loads and supports cancellation and eviction.

```swift
import RealityKit
import Foundation

@MainActor
actor BoundedModelLoader {
    private var cache: [URL: ModelEntity] = [:]
    private var inFlight: Set<URL> = []
    private let concurrencyLimit: Int

    init(concurrencyLimit: Int = 3) {
        self.concurrencyLimit = concurrencyLimit
    }

    func load(_ url: URL) async throws -> ModelEntity {
        if let model = cache[url] { return model }
        while inFlight.count >= concurrencyLimit {
            try await Task.sleep(nanoseconds: 50_000_000) // 50ms backoff
        }
        inFlight.insert(url)
        defer { inFlight.remove(url) }
        do {
            let entity = try await ModelEntity.load(contentsOf: url)
            cache[url] = entity
            return entity
        } catch {
            throw error
        }
    }

    func evict(_ url: URL) {
        cache[url]?.destroy()
        cache.removeValue(forKey: url)
    }
}
```

Tune the concurrency limit according to device memory and I/O characteristics. Ensure cancellation paths are exercised in tests; non-cancelled tasks can waste CPU and battery. Expose runtime counters (instruments-friendly signposts) for in-flight loads and cache size so memory spikes can be correlated to loader behavior.

## 4. Memory Management And Resource Lifecycle
### Explicitly Release GPU Resources
Anti-pattern → Preferred: relying purely on ARC can leave GPU-backed textures and ModelEntity resources alive longer than intended. Call Entity.destroy() (or destroy() on replaced resources) and evict caches deterministically when appropriate.

```swift
// Deterministic destroy before eviction
if let model = cache[url] {
    model.destroy()
    cache.removeValue(forKey: url)
}
```

When sessions are long or multiple heavy scenes can appear in a single app session, evict large assets deterministically. Allow ARC to handle short-lived objects, but evict large GPU-backed assets when they are no longer needed.

Include longer-running tests that exercise loading and eviction paths and observe resident GPU and memory usage to ensure resources are released as expected.

## 5. Physics And Update Loop Costs
### Reduce Physics Complexity And Isolate Frequent Updates
Anti-pattern → Preferred: running full-world physics for many interactive objects can be expensive. Limit physics to interactive subsets or run physics at a lower update rate and synchronize transforms at well-defined boundaries.

Full physics is appropriate for small, constrained scenes. For dense crowds or background objects, consider sampled physics or simplified collision models. Replace per-frame heavy work with event-driven updates where feasible.

Mark physics steps with OSSignposter and capture Time Profiler traces during complex interactions. Add CI assertions that a physics step does not exceed a configured millisecond budget under representative test scenarios.

> Add signposts around heavy boundaries (loads, physics steps, material swaps); they reduce time-to-fix when regressions appear.

## Tradeoffs And Pitfalls
- Throughput vs latency: batching geometry and merging meshes improves throughput but can increase latency for immediate manipulations. Prefer lower-latency approaches for direct-manipulation interactions and higher throughput for background populations.
- Preload risk: aggressive preloading reduces stalls but raises peak memory and power use; devices with constrained memory typically reveal problems first. Use sampled rollouts and telemetry to validate preload strategies.
- Instrumentation impact: excessive tracing can change timing. Gate heavy traces to debug builds or sampled sessions to preserve production characteristics.

## Validation & Observability
Instrument and gate changes with these tools and tests:
- OSSignposter to mark async boundaries for ModelEntity loads, physics steps, and scene updates.
- Instruments Time Profiler and Allocations templates to capture shader compilations, CPU hotspots, and resident memory usage.
- MetricKit to collect post-release telemetry for thermal and crash signals.
- os_log for structured runtime events correlated with signposts.
- XCTest performance assertions and async expectations that run on-device against representative scenes.

Include signpost data in CI artifact bundles and use telemetry signals to gate rollouts where practical. Run automated on-device tests that assert frame-time budgets and memory growth to provide deterministic rollout gates.

## Practical Checklist
- [ ] Inventory heavy assets and convert to GPU-friendly formats (base color, metallicRoughness, compressed textures).
- [ ] Add OSSignposter events around scene updates, asset loads, and physics steps.
- [ ] Implement an async prefetch pipeline using a bounded loader actor with cancellation for ModelEntity.load(contentsOf:).
- [ ] Replace deep transform hierarchies with flat entity groups where transforms update frequently.
- [ ] Add XCTest performance assertions and integrate MetricKit collection into rollout gating.
- [ ] Implement deterministic resource eviction (call Entity.destroy() or cache eviction) and run longer-session tests on devices that represent your target fleet.

## Closing Takeaway
Small, deliberate changes to scene structure, asset loading, and resource eviction improve stability when using RealityKit on platforms with constrained thermal and power budgets. Use a bounded loader, bake and compress static textures, flatten hot transform paths, and instrument with OSSignposter and Instruments. Gate rollouts with on-device tests and telemetry so runtime regressions surface before they affect many users.

## Swift/SwiftUI Code Example

```swift
import SwiftUI
import RealityKit

actor AssetLoader {
    let maxConcurrent: Int
    private var activeLoads = 0
    init(maxConcurrent: Int = 3) { self.maxConcurrent = maxConcurrent }
    func loadModel(from url: URL) async throws -> ModelEntity {
        // Backpressure: bound concurrent loads to avoid spikes
        while activeLoads >= maxConcurrent { await Task.yield() }
        activeLoads += 1
        defer { Task { await self.decrement() } }
        return try await ModelEntity.loadAsync(contentsOf: url)
    }
    private func decrement() { activeLoads = max(0, activeLoads - 1) }
}

struct BoundedLoadView: View {
    @State private var entities: [ModelEntity] = []
    let urls: [URL]
    let loader = AssetLoader(maxConcurrent: 2) // tuned for device budget

    var body: some View {
        VStack {
            Button("Load Models") {
                Task { await loadAll() }
            }
            Text("Loaded: \(entities.count)")
        }
    }

    func loadAll() async {
        var loaded: [ModelEntity] = []
        for url in urls {
            do {
                let model = try await loader.loadModel(from: url)
                // Minimal parenting; keep shallow hierarchies in app logic
                model.name = url.lastPathComponent
                loaded.append(model)
            } catch {
                // handle per-asset failure without cancelling whole batch
                continue
            }
        }
        // once done, publish on main thread
        await MainActor.run { entities = loaded }
    }
}
```

## References

- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
