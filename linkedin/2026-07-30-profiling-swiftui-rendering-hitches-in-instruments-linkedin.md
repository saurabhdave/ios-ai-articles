SwiftUI scroll hitches often aren’t from a single slow view; they can come from the main thread missing a frame while recomposition, layout, and drawing stack up. You won’t reliably isolate a stall by eyeballing code — you generally need a Release trace on a physical device.

- Start in `Core Animation` to spot frame drops
- Pivot to the same interval in `Time Profiler` for attribution
- Use the `SwiftUI` instrument to see which view `body` values recomposed

What’s your go-to sequence in Instruments for chasing a hitch, and where do you usually find the bottleneck?

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
