# UI design

The Electron application uses a quiet white/off-white desktop shell inspired by the supplied reference. Native window controls follow the platform; no fake macOS traffic lights appear on Windows.

## Tokens

| Token | Value |
| --- | --- |
| Background | #ffffff |
| Surface | #f7f7f5 |
| Hover surface | #f1f1ef |
| Primary text | #111111 |
| Secondary text | #6f6f6b |
| Border | #e6e6e3 |
| Radii | 10px / 14px / 20px / pill |

The sidebar stays fixed. Main content uses a small fade/vertical transition. Status colors are limited to recording red, verified knowledge green, and the voice orb's soft blue/cyan/green gradients. Shared controls use locally owned shadcn source and Radix accessibility primitives.

## Motion and overlay

Hover and press feedback stays short; content transitions take 240ms. The orb's layout spring uses stiffness 420 and damping 32. Toolbar buttons reveal with 25ms offsets. Native overlay bounds expand before DOM animation and contract after the exit transition. The orb stays anchored while controls expand outward. Pointer hit testing passes through transparent empty regions. Focus is opt-in so questions do not steal focus from the task.

Idle decoration does not continuously animate. Voice activity, question arrival, toolbar expansion and meaningful state changes can animate. Reduced-motion preferences disable CSS motion and inform Motion's layout transitions.

## Real-data rule

No seeded names, workflows, screenshots, conversations, progress numbers or exercises. Empty states explain a real next action. Loading and error states represent actual work. Generated practice is clearly labeled hypothetical and must cite confirmed knowledge. The UI never substitutes a sample response when a provider fails.
