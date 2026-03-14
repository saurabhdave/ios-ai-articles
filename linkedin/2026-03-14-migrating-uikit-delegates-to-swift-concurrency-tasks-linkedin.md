UI delegates work — until they don't. For complex screens, moving delegate flows into Swift Concurrency primitives can reduce callback hell and give you structured cancellation and clearer control flow — but it needs to be done deliberately.

Practical takeaways:
- Start view-scoped: begin with delegates owned by a view or controller (e.g., UITableView, UITextField, CLLocationManager).
- Encapsulate: build small adapter types that own delegate registration and expose AsyncStream or async functions so callers get a simple async API.
- Instrument and test: log adapter lifecycle, yields, and cancellations; add unit tests that verify attach/detach behavior.
- Be compatible: guard for runtime availability and keep delegate fallbacks for environments where you can’t use concurrency APIs.

Tradeoffs to watch for: high-frequency, low-latency callbacks (audio/video, tight sensor loops) may not map directly to AsyncStream without careful design. In those cases prefer native delegate paths for the hot loop and expose higher-level state or throttled updates via concurrency APIs.

Example adapter shape:
AsyncStream { continuation in
 // translate delegate callbacks -> continuation.yield(...)
 // handle continuation.onTermination { ...detach... }

Want a short adapter audit checklist or to compare patterns for specific delegates you’re migrating? Let’s discuss practical migration strategies and pitfalls you’ve seen.

#iOS #Swift #Concurrency #UIKit #Architecture
