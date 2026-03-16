If your codebase still uses URLSession completion handlers, moving to Swift async/await can simplify call sites — but it also changes how cancellation, error propagation, and observability are handled. Here’s a pragmatic, low-risk approach to consider.

- Inventory completion-style usages (IDE search, SwiftSyntax codemods) before changing public APIs.
- Start with isolated networking modules. Use continuation-based wrappers as short-lived bridges and URLProtocol for deterministic tests.
- Ensure wrappers forward Task cancellation to the underlying URLSessionTask (e.g., call URLSessionTask.cancel() when the Task is cancelled) and capture URLSessionTaskMetrics/signposts for observability.
- Validate with async XCTest cases covering success, error, retry, and cancellation paths. Stage rollouts behind feature gates where appropriate.

Tradeoff: a big-bang refactor can reduce hybrid complexity but increases blast radius — for production-critical apps, prefer per-module migration.

Callout: rely on Foundation (URLSession, URLProtocol) and Swift’s structured concurrency primitives while you migrate.

Have you encountered cancellation or observability gaps during a migration? What patterns worked for your team?

#iOS #Swift #SwiftConcurrency #EngineeringLeadership #Observability
