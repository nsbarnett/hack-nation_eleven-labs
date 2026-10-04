# Floating assistant setup

1. Build with `cd app` and `npm run build:web`. Download the ZIP from Settings, or use `release/extension/apprentice-extension.zip`.
2. Extract it. In Chrome visit `chrome://extensions`; in Edge visit `edge://extensions`.
3. Enable Developer mode, choose **Load unpacked**, and select the extracted folder containing `manifest.json`. The local `release/extension/unpacked` folder is ready to load directly.
4. Open extension options. Enter the exact Apprentice origin shown in the app's Settings. Use the published HTTPS origin; localhost/127.0.0.1 HTTP is allowed for development. Paths, credentials and API keys do not belong here.
5. Choose **Save URL & enable website access**, grant the browser's permission, then reload Apprentice and the websites where you want the orb. Keep one Apprentice workspace tab open.

The browser owns permission dialogs. Record from the orb opens the app's capture dialog; click Start recording there. Stop, Mute and text context operate on the current session. Voice focuses the app and requests microphone capture there; a second Voice action ends it. The extension neither reads underlying page text nor records screens itself.

Click to expand/collapse; hover only displays labels. Drag more than six pixels to move the orb. Focus it and use Alt + arrows for keyboard positioning. Escape closes a panel. Positions are clamped to the tab viewport and stored locally in CSS coordinates.

Disconnection disables actions except Open App. Reconnect obtains a fresh snapshot. Commands carry unique IDs and session/question identity and are never replayed automatically. A stale command cannot answer a different question.

## Boundaries

- Optional website access enables injection. Protected browser pages, extension stores, some PDF viewers, sandboxed pages and site policies can prevent it.
- The host receives geometry messages only. Questions and notes stay in extension-owned iframes; media and keys never pass through the extension.
- Outside visible panels, clicks pass through. A full-page transparent surface exists only during an active drag, then is removed.
- Capture shows **Recording locally · Privacy review pending**. Screen questions follow approved-frame analysis.
- The orb cannot float over native apps. Entire-display capture may include it; choose a different surface or collapse it as appropriate.

## Update and remove

Rebuild, replace the extracted folder, click Reload on the extensions page, and reload the app/websites. Removing the extension removes its URL/position, not Apprentice recordings. Delete those in the app's Settings or Privacy Review.

No store publication/signing is performed. Replit serves the ZIP but cannot automatically install extensions into visitors' browsers.
