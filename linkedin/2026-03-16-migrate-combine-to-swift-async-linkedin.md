Stop treating migration from Combine to async/await as a mechanical find‑and‑replace — it’s a different execution model that affects timing, cancellation, and demand semantics.

Practical roadmap I use with teams:
- Inventory and pick low‑risk wins first (network layer: replace Combine publishers like dataTaskPublisher with URLSession’s async data(for:) where appropriate).
- Bridge instead of ripping out: use AsyncThrowingStream ↔ PassthroughSubject patterns to roll changes out incrementally.
- Test cancellation behavior and profile before/after (time and allocation profiling) — subtle timing differences can hide regressions.

Decision point guidance: prefer Task and structured concurrency for scoped, parent‑controlled work; keep Combine where you need multicasting or explicit demand/backpressure semantics.

Operational notes: add XCTest async tests, use tracing/os_signpost where helpful, and stage rollouts behind feature flags so timing changes surface safely.

What migration taught you the most or where did you hit unexpected breakage? Let’s compare notes.

#iOS #Swift #Architecture #Concurrency #EngineeringLeadership
