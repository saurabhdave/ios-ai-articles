Silently divergent local build scripts once caused a release failure for me — version your build-time tools and move them out of per-developer shell scripts.

- Put generators, linters, and asset processors into `PackagePlugin` targets so `Package.swift` pins tooling behavior and reduces configuration drift.
- Use `BuildToolPlugin` when outputs must exist before compilation and `CommandPlugin` when tasks can be optional or developer-invoked; validate plugin runs in CI with smoke jobs that exercise `xcodebuild` and `swift build`.
- Write outputs to derived or package build output directories (not package source), use `Process`/`FileManager`, and fail fast with clear diagnostics so CI logs are actionable.
- Add `XCTest` coverage for deterministic outputs and consider `os_signpost` for tracing long-running paths during profiling.

Choose `BuildToolPlugin` for compiler-required outputs and `CommandPlugin` for opt-in utilities.

How have your teams handled rollout and rollback for package plugins across multiple Xcode versions — what worked, what didn’t, and what signals did you use to decide a rollback?

#iOSDev #Swift #Xcode #SwiftPM #iOS
