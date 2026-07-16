Xcode saying “Compiling Swift” when your change was trivial? In mixed Swift/Obj‑C workspaces, that’s often `swiftc` and `Clang` reparsing broad header trees on every file. Make modules explicit and you prebuild once, then reuse.

- Shift work upfront: explicit modules compute the dependency graph and prebuild modules deterministically, turning random rebuilds into predictable reuse across targets.
- Rollout safely: start with leaf frameworks, enable in Release/CI first, then Debug; set `Build with Explicit Module` and add `-explicit-module-build` (or SwiftPM’s `.unsafeFlags` for selected targets).
- Fix headers: keep umbrella headers in‑module only, author `module.modulemap` where needed, and reproduce CI issues locally with `xcodebuild` and matching `HEADER_SEARCH_PATHS`.
- Stabilize caches: pin the toolchain, keep a stable DerivedData location, and track timing with `xcodebuild -showBuildTimingSummary`; instrument custom steps using `OSSignposter` for clear boundaries.

Choose explicit modules when targets expose deep C/Objective‑C surfaces or are widely reused; keep implicit builds for tiny Swift‑only targets

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
