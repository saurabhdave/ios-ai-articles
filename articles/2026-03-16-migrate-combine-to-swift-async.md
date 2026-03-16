# Migrate Combine to Swift async/

Replace long Combine chains with Swift async/await and your code often becomes easier to reason about. Migration is not a mechanical find-and-replace: execution timing, cancellation semantics, and backpressure differ. This guide gives a pragmatic, testable roadmap for migrating incrementally with minimal release risk.

## Why This Matters For iOS Teams Right Now

Apple frameworks increasingly expose async entry points. Task-based structured concurrency makes linear, sequential logic easier to read and reason about and provides a hierarchical cancellation model that differs from Combine’s token-based approach. That change in model affects timing, allocation, and cancellation propagation — all of which can surface as behavioral or performance regressions if you migrate blindly.

When to choose which model:
- Prefer async/await and Task for linear, sequential flows and when using APIs that already provide async entry points.
- Keep Combine when you need rich operator composition, multicasting, or explicit demand/backpressure semantics.

Operational note: add observability and stage rollouts; migrations can subtly change behavior even when tests pass.

> Prefer incremental bridges over wholesale rip-and-replace — you’ll find bugs earlier and minimize blast radius.

## 1. Inventory & Prioritization

### Find Combine Sites And Quick Wins
Scan your codebase for Publisher types, AnyCancellable, and common operators such as sink, flatMap, and eraseToAnyPublisher. Use SourceKit-LSP or SwiftSyntax where possible to get a precise list; otherwise a targeted text search is a useful start.

Decision criteria for what to migrate first:
- Migrate isolated, well-tested modules with limited operator complexity.
- Defer modules that rely on multicasting, dense operator graphs, or custom backpressure logic.

Testing and rollout guidance:
- Network-layer conversions are the lowest-risk wins — replace dataTaskPublisher with URLSession data(for:) inside async functions.
- Add XCTest async tests for success, error, and cancellation paths.

## 2. Migration Patterns: Idiomatic Translations

### Direct API Mapping For Networking
Replace publishers backed by URLSession.dataTaskPublisher with async URLSession APIs inside a Task or async function. Prefer Task when you want structured parent/child lifetimes; use continuations only to wrap callback-based APIs that have no async alternative.

Decision criteria:
- Choose Task for clear ownership and parent-controlled cancellation.
- Use `withCheckedThrowingContinuation` only when necessary and audit resume paths carefully.

Operational note:
- A continuation that is never resumed will hang awaiting code; write tests that exercise all paths and consider timeouts for safety.

### Translating Event Streams To `AsyncSequence`
For sources that emit repeated events (text input, socket messages, file notifications), translate publishers into `AsyncSequence` using `AsyncThrowingStream` or `AsyncStream` so consumers can use for await.

Decision criteria:
- Use `AsyncThrowingStream` when consumers iterate with for await and a simple producer/consumer model suffices.
- Keep Combine when you need multicasting or demand-based flow control.

Operational note:
- Bridging a high-rate publisher to `AsyncSequence` can change allocation and scheduling. Profile representative scenarios.

## 3. Interoperability: Combine and Async Coexistence

### Bridging Patterns
Incremental migration will require interop bridges:
- Combine → async: subscribe to a publisher and yield values via `AsyncThrowingStream` to present an `AsyncSequence`.
- async → Combine: publish values from async code using a PassthroughSubject or a custom Publisher wrapper.

Decision criteria:
- Bridge when it reduces risk and lets you ship incrementally; replace fully when semantics are simple and tested.

Operational/testing note:
- Ensure cancellation propagates both ways. Add tests that cancel from the Combine side and from the Task side and verify resources are released.
- Avoid bridging in tight loops or hot paths where per-event allocations matter.

## 4. Testing, Observability, And Rollout Strategies

### Test Patterns And Telemetry
Use XCTest async tests for async logic, and XCTestExpectation where you need more precise timing control. Instrument boundaries with os_signpost and structured logging tied to Task lifetimes and important events.

Practical steps:
- Add unit and integration coverage for any module you replace.
- Stage rollouts behind feature flags or canary cohorts for user-facing changes.
- Add lightweight telemetry to detect regressions in latency, error rates, and allocations.

Operational/testing note:
- Profile with Instruments (Time Profiler and Allocations) before and after migration to capture CPU and memory differences.

## 5. Tradeoffs, Pitfalls, And Engineering Guidance

### Concrete Tradeoffs
- Cancellation and Lifetimes: Structured concurrency gives hierarchical cancellation; Combine uses AnyCancellable tokens. Use Tasks for scoped lifetimes and Combine when subscription graphs are long-lived or shared.
- Backpressure: Combine exposes demand signaling. `AsyncSequence` does not provide the same demand control — preserve Combine where demand matters or redesign the flow.
- Debugging and Readability: Async/await often clarifies sequential flows, but complex reactive graphs benefit from operator reasoning and composability.

Common pitfalls and mitigations:
- Continuation safety: audit every `withCheckedThrowingContinuation` usage for exhaustive resume paths and add tests for success, error, and cancellation.
- Threading assumptions: many async APIs resume on background threads — annotate UI code with `@MainActor` or wrap UI updates with await MainActor.run { }.
- Allocation and scheduling changes: validate hot paths with profiling.

Practical iOS guidance:
- Prefer Task for new structured work; prefer `@MainActor` for UI-affecting functions.
- Keep Combine for multicasting, operator-heavy transformations, or when explicit demand must be honored.

## Implementation Checklist

- Inventory:
 - Use code analysis to list Publisher and AnyCancellable sites and common operator call sites.
- Prioritize:
 - Convert isolated network-layer usages first where async APIs exist.
 - Target well-tested modules with limited operator complexity.
- Bridge:
 - Use `AsyncThrowingStream` to expose `AsyncSequence` from publishers when needed.
 - Use PassthroughSubject or custom Publishers to surface async work to Combine consumers.
- Test & Observe:
 - Add XCTest async tests and os_signpost markers around conversions.
 - Profile with Instruments before and after changes.
 - Add telemetry to monitor real-world behavior after rollout.
- Rollout:
 - Gate changes with feature flags and canary cohorts.
 - Monitor cancellation behavior, latency, and allocation differences.
- Safety:
 - Audit all continuation usage for complete resume paths.
 - Confirm UI code runs on the main actor where required.

- Quick scanning summary:
 1. Inventory and pick low-risk network modules.
 2. Bridge where needed instead of replacing everything at once.
 3. Test cancellations and profile runtime behavior.
 4. Roll out gradually with telemetry.

## Closing Takeaway

Migrating from Combine to Swift async/await can simplify many control flows and reduce boilerplate for sequential logic, but it changes execution characteristics that matter in production: timing, backpressure, and cancellation semantics. Start with low-risk modules like networking, use bridges to reduce blast radius, and instrument heavily with tests, logging, profiling, and telemetry. Prefer Task and async for structured sequential work; retain Combine where multicasting, operator composition, or demand control are critical. When in doubt, bridge and observe before you replace.

## Swift/SwiftUI Code Example

```swift
import SwiftUI
import Observation
import Foundation

// Simple Photo model matching a typical JSON response.
struct Photo: Identifiable, Codable, Hashable {
    let id: Int
    let title: String
    let thumbnailUrl: URL
}

// Network layer using async/await.
enum NetworkError: Error {
    case invalidURL, invalidResponse, decodingError(Error)
}

struct NetworkClient {
    static func fetchPhotos(matching query: String, limit: Int = 25) async throws -> [Photo] {
        guard var comps = URLComponents(string: "https://jsonplaceholder.typicode.com/photos") else {
            throw NetworkError.invalidURL
        }
        comps.queryItems = [URLQueryItem(name: "q", value: query), URLQueryItem(name: "_limit", value: "\(limit)")]
        guard let url = comps.url else { throw NetworkError.invalidURL }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw NetworkError.invalidResponse
        }
        do {
            let decoder = JSONDecoder()
            return try decoder.decode([Photo].self, from: data)
        } catch {
            throw NetworkError.decodingError(error)
        }
    }
}

// Debouncer implemented inside the model using Task cancellation - replaces Combine's debounce operator.
@Observable
final class PhotoSearchViewModel {
    // Observable state.
    var searchQuery: String = ""
    var results: [Photo] = []
    var isLoading: Bool = false
    var errorMessage: String? = nil

    // Internal cancellation handle for the current active search debounce/fetch.
    private var currentSearchTask: Task<Void, Never>? = nil

    // Called by the UI when the query changes. Debounces rapid changes and performs an async fetch.
    func queryChanged() {
        // Cancel any pending debounce/fetch.
        currentSearchTask?.cancel()

        // If query is empty, clear results immediately.
        let query = searchQuery.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else {
            results = []
            isLoading = false
            errorMessage = nil
            return
        }

        // Start a new Task that waits for the debounce interval, then performs the fetch.
        currentSearchTask = Task { [weak self] in
            // Debounce interval: 300 ms
            do {
                try await Task.sleep(nanoseconds: 300 * 1_000_000)
            } catch {
                // Task was cancelled during debounce.
                return
            }

            if Task.isCancelled { return }

            await MainActor.run {
                self?.isLoading = true
                self?.errorMessage = nil
            }

            do {
                // Perform network fetch using async/await.
                let fetched = try await NetworkClient.fetchPhotos(matching: query, limit: 50)

                if Task.isCancelled { return }

                // Update UI state on the main actor.
                await MainActor.run {
                    self?.results = fetched
                    self?.isLoading = false
                    self?.errorMessage = nil
                }
            } catch {
                // If cancelled, just return.
                if Task.isCancelled { return }

                // Map or display the error message on the main actor.
                await MainActor.run {
                    self?.results = []
                    self?.isLoading = false
                    switch error {
                    case NetworkError.invalidURL:
                        self?.errorMessage = "Invalid URL."
                    case NetworkError.invalidResponse:
                        self?.errorMessage = "Server error."
                    case NetworkError.decodingError(let inner):
                        self?.errorMessage = "Decoding error: \(inner.localizedDescription)"
                    default:
                        self?.errorMessage = error.localizedDescription
                    }
                }
            }
        }
    }
}
```

## References

- [Swift Concurrency](https://developer.apple.com/documentation/swift/concurrency)
- [Combine](https://developer.apple.com/documentation/combine)
- [Swift Documentation](https://www.swift.org/documentation/)
