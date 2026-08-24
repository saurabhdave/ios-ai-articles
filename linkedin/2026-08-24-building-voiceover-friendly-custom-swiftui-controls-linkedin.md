Custom SwiftUI controls can look right and still fail VoiceOver: actions aren’t discoverable, labels don’t reflect state, and focus jumps can cause scroll stutter. Treat the control’s accessibility as part of its API, not a detail of its children. ♿️

- Model the control as one element with `accessibilityElement(children:

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
