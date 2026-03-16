# Migrate URLSession to Swift async/await

Swapping URLSession completion handlers for async/await can clean up call sites quickly — but in real apps it changes cancellation semantics, error propagation, and observability. This article gives a pragmatic, low-risk path to migrate networking to Swift concurrency while keeping testability, cancellation correctness, and rollout safety in mind.

## Why This Matters For IOS TEAMS RIGHT NOW
Swift concurrency is the modern model for asynchronous code on Apple platforms. Foundation APIs, including URLSession, provide async variants; moving to them often improves readability and makes cancellation more explicit.

Adopting async/await across a large app without a plan can create hybrid flows where Task cancellation and URLSessionTask cancellation are not automatically aligned. That divergence can introduce subtle bugs during cancellations, retries, and lifecycle transitions.

Recommendation: migrate incrementally — convert isolated networking modules first, gate changes behind feature flags if needed, and validate cancellation behavior and observability end-to-end.

## 1. INVENTORY & MIGRATION STRATEGY
### Locate And Replace
Tools and approaches:
- Use IDE refactors and source tools (for example, editor refactoring and SwiftSyntax-based codemods) to locate completion-handler patterns like URLSession.dataTask(with:completionHandler:).
- Identify call sites and trace which modules own callers to decide the scope of change.

When to choose which approach:
- Whole-module migration: appropriate when a team owns both the HTTP abstraction and its callers; you can replace internal implementations and update clients together.
- Bridging wrappers: appropriate when many callers (or external modules) still expect completion handlers or you need to keep a stable ABI surface while migrating incrementally.

Operational/testing note:
- Validate cancellation and state transitions with integration tests and runtime observation. Roll out changes per module or cohort and monitor for behavioral regressions.

### Decision Criteria Summary
- Small control surface → consider full refactor.
- Many consumers or external callers → prefer bridging wrappers.
- Need to preserve existing delegate-based metrics/telemetry → keep the delegate path behind a gate while you migrate.

## 2. WRAPPING LEGACY APIS SAFELY
### Continuations And Delegate Bridges
Practical building blocks:
- withCheckedThrowingContinuation (and its unchecked variant) is useful for wrapping single-completion callback APIs into async functions.
- URLProtocol is commonly used for stubbing network responses in tests.

When to use continuations:
- Use continuations for simple one-shot callbacks (success or error).
- Avoid simple continuation wrappers for complex, stateful delegate flows. Those are better expressed as async primitives or an actor-protected state machine that models the state transitions clearly.

Operational/testing note:
- Tests must assert that continuations are resumed exactly once. Add tests for success, failure, timeout, and duplicate-callback scenarios using XCTest’s async support and URLProtocol for stubbing.

### Practical Wrapper Pattern (concept)
- Resume the continuation from the appropriate delegate or completion callback.
- Keep a reference to the created URLSessionTask so you can cancel it from a Task cancellation handler.
- Consider emitting telemetry spans around the wrapper to preserve observability of request boundaries.

A minimal pattern:
- Create the URLSessionTask and start it.
- Register a Task cancellation handler that cancels the URLSessionTask.
- Resume the continuation in the response callback (ensuring single resume semantics).
- Clean up any delegate/state references after resumption.

## 3. ERROR HANDLING, RETRIES, AND CANCELLATION
### Structured Concurrency And Networking
Patterns and primitives:
- Use Task and TaskGroup when you need structured, cancellable coordination between multiple async operations.
- Use async let and serial Tasks for simpler composition where ordering and cancellation boundaries are straightforward.
- Avoid Task.detached for requests that should inherit local task priority, context, or cancellation unless you intentionally need detached behavior.

Operational/testing note:
- Retry loops should check Task.isCancelled between attempts and abort promptly when cancellation is observed.
- Capture and record retry events and backoff information in logs and metrics to make rollouts observable.
- Use URLSessionTaskMetrics or delegate callbacks where you need timing and network-level data.

### Failure Modes To Watch
- Cooperative cancellation: Swift concurrency cancellation is cooperative; you must wire Task cancellation to underlying URLSessionTask.cancel() in wrappers.
- Detached tasks and poorly scoped Tasks can ignore intended cancellation and actor isolation rules — review where you create Tasks relative to lifecycle owners (views, view models, actors).

## 4. TESTING & OBSERVABILITY
### Deterministic Tests And Production Signals
Testing and observability tools commonly used:
- XCTest async tests for unit and integration testing.
- URLProtocol for deterministic stubbing of network responses.
- Instrumentation and telemetry (such as signposts and collected task metrics) to observe runtime behavior.

When to choose testing types:
- Unit tests with URLProtocol stubs for deterministic responses and for exercising error and cancellation paths.
- Integration or staging tests against a real backend to validate authentication flows, redirects, and timing under realistic conditions.

Operational/testing note:
- For cancellation tests, assert both that the Swift Task observed cancellation and that the underlying URLSessionTask was cancelled (where applicable).
- Add CI checks or pre-merge tests that detect dangling tasks or leaked resources stemming from mis-resumed continuations.

### Observability Checklist
- Emit request-level spans or signposts to mark request start/end for tracing.
- Surface URLSessionTaskMetrics or equivalent timing/size information through your telemetry pipeline.
- Tag retries, cancellations, and error classes so canary rollout dashboards can differentiate regressions.

## 5. TRADEOFFS AND PITFALLS
### Practical Tradeoffs And Common Pitfalls
- Migration speed vs safety: a bulk refactor reduces temporary complexity but increases blast radius. Per-module or per-feature migration reduces risk for high-availability apps.
- Continuation complexity: continuations are fine for small bridges; for multi-callback or stateful flows consider refactoring into async primitives or an actor to manage state and lifecycle.
- Cancellation semantics: Swift concurrency cancellation is cooperative. If legacy paths didn’t cancel underlying URLSessionTasks, your wrappers must do so explicitly.

Operational/testing note:
- Mis-resumed continuations (never resumed or resumed multiple times) cause hangs or crashes. Add unit tests that simulate timeouts and duplicate-callback scenarios and monitor for dangling tasks in runtime diagnostics.

- Make cancellation contracts explicit in your public interfaces and document expectations for callers. If you must preserve completion-handler APIs for compatibility, provide well-documented async bridges and migration guidance for clients.

## CHECKLIST BEFORE SHIP
- Inventory: locate completion-style URLSession usages using source analysis tools.
- Migration plan: define per-module gates and rollout cohorts.
- Wrappers: implement continuation-based bridges that include timeout handling and Task cancellation hooks which cancel the underlying URLSessionTask.
- Testing: add XCTest async tests + URLProtocol stubs covering success, error, retry, and cancellation scenarios.
- Observability: emit request spans/signposts and collect task timing metrics; surface retries and cancellations in dashboards.
- Rollout: stage changes incrementally and monitor error and latency signals closely during canary periods.

## CLOSING TAKEAWAY
Migrating URLSession usage to async/await reduces boilerplate and clarifies control flow, but it requires attention to cancellation, testing, and observability. Start with isolated networking modules, use continuation wrappers only for small bridges, and validate cancellation and metrics end-to-end before broad rollout. Be explicit about cancellation contracts and measure operational signals during staged rollouts so you can detect and remediate regressions quickly.

## Swift/SwiftUI Code Example

```swift
import SwiftUI
import Foundation
import Observation

// Simple Decodable model matching a common public test API
struct Post: Identifiable, Decodable {
    let userId: Int
    let id: Int
    let title: String
    let body: String
}

// Centralized error type for networking layer
enum NetworkError: Error, LocalizedError {
    case invalidURL
    case invalidResponse(statusCode: Int)
    case decodingError(Error)
    case other(Error)
    
    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid URL."
        case .invalidResponse(let code): return "Server returned status code \(code)."
        case .decodingError(let e): return "Decoding failed: \(e.localizedDescription)"
        case .other(let e): return e.localizedDescription
        }
    }
}

// Lightweight network client using async/await and URLSession
struct NetworkClient {
    private let session: URLSession
    
    init(session: URLSession = .shared) {
        self.session = session
    }
    
    // Generic GET request that decodes JSON into Decodable T
    func getJSON<T: Decodable>(_ url: URL, decoder: JSONDecoder = JSONDecoder()) async throws -> T {
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: request, delegate: nil)
        } catch {
            throw NetworkError.other(error)
        }
        
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            let code = (response as? HTTPURLResponse)?.statusCode ?? -1
            throw NetworkError.invalidResponse(statusCode: code)
        }
        
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw NetworkError.decodingError(error)
        }
    }
}

// Observable model using Swift Observation for state
@Observable
final class PostsStore {
    // UI-facing state
    var posts: [Post] = []
    var isLoading: Bool = false
    var lastErrorMessage: String? = nil
    var query: String = "" // simple client-side filter
    
    // Dependencies
    private let client: NetworkClient
    // Track the currently running fetch task so we can cancel previous requests if needed
    private var currentTask: Task<Void, Never>? = nil
    
    init(client: NetworkClient = NetworkClient()) {
        self.client = client
    }
    
    // Public fetch function. Cancels any in-flight fetch and starts a new one.
    func refreshPosts() {
        // Cancel previous task if still running
        currentTask?.cancel()
        
        isLoading = true
        lastErrorMessage = nil
        
        currentTask = Task { [weak self] in
            // Keep a strong reference for the duration of this task
            guard let self = self else { return }
            
            do {
                let url = URL(string: "https://jsonplaceholder.typicode.com/posts")!
                let fetched: [Post] = try await self.client.getJSON(url)
                
                // Respect cancellation if it happened during the network call
                if Task.isCancelled { return }
                
                // Apply a simple client-side filter based on `query`
                let filtered: [Post]
                if self.query.isEmpty {
                    filtered = fetched
                } else {
                    let q = self.query
                    filtered = fetched.filter {
                        $0.title.localizedCaseInsensitiveContains(q) ||
                        $0.body.localizedCaseInsensitiveContains(q)
                    }
                }
                
                // Update state on success
                self.posts = filtered
            } catch {
                // If the task was cancelled, bail out silently
                if Task.isCancelled { return }
                // Convert errors to a user-facing message
                self.lastErrorMessage = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            }
            
            // Ensure loading flag is cleared regardless of outcome
            self.isLoading = false
        }
    }
}
```

## References

- No verified external references were available this run.
