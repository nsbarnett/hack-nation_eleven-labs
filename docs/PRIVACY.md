# Local review and timed redaction

Browser capture and disclosure are separate. Cloud consent alone never permits a screen upload: the local rendered recording must also be explicitly approved at the server's current privacy revision.

## Local state and detection

IndexedDB `apprentice-media-v1`, schema version 2, has guest/workflow-scoped `assets`, `chunks`, and `reviews` stores. Version-1 media is retained and unreviewed. Segments carry start time, duration and dimensions. Drafts store finding categories/bounds, resolutions, cuts, cover intervals/keyframes, scan progress/gaps, derivative links and completed analysis selections. OCR text is neither persisted nor sent to the server.

Capture writes bounded chunks. One live OCR job is allowed; busy samples are skipped instead of queued. After stop, the postscan decodes sequentially, compares small thumbnails for possible cuts/dimension changes, and OCRs at half-second intervals and cuts (maximum 1,500 OCR frames per segment). Failed/interrupted/canceled scans are labeled incomplete. Progress counts completed frames; users can review manually when there are gaps.

Tesseract's worker, WASM and English data are packaged under `app/dist/ocr`, served from the same origin. There is no external OCR service/CDN. The detector suggests emails, formatted phones, Luhn-valid cards, recognizable credentials and label-associated account identifiers. False positives and misses are expected. Brief content between samples, tiny/low-contrast text, general names/addresses and faces may be missed.

## Covers and rendering

Coordinates are normalized per segment. Cover intervals are half-open; keyframes interpolate only within them. Detected screen cuts/dimension changes require splitting before rendering. Users can split manually because automatic cut detection can miss transitions. Covers are opaque rectangles with a small pixel margin. Any encoded frame overlapping the interval is covered in full, conservatively extending the cover by up to one frame.

Mediabunny/WebCodecs decode and re-encode video in a worker. Append-only WebM chunks reach IndexedDB with backpressure and a separate 100 MB derivative budget. Finishing a render does not approve it: users preview and explicitly approve, including zero-findings or incomplete scans.

Failed/unsupported encoders, quota failures or cancellation never yield approved exports. Partial derivatives are removed; originals/edits remain. Reload recovers drafts and marks interrupted work. Library only resolves complete, matching-revision redacted assets. Original images are never thumbnail/download fallbacks. Analysis JPEGs are decoded from the rendered video, applying the identical covers.

Originals stay local until explicit deletion. Deleting originals after approval retains the derivative but prevents further original edits. Browser eviction and clearing site data can also remove media; preserve important approved exports.

## Server boundary

Authenticated same-origin `privacy-reset` and `privacy-approve` commands require the expected revision. Committed edits increment it, revoke approval, clear derived observations/knowledge/practice and cancel pending results. Expert-entered text remains separate. `/api/frame` rejects live browser uploads. `/api/reviewed-frame` requires the current idle session and approved revision, validates metadata/payload bounds, and runs the bounded observer. Successful analyzed-frame IDs are persisted; a queued/failed request is not reported as completed analysis.

The browser selects a frame every ten seconds and waits for each model job. The service holds at most three frames in memory; PostgreSQL stores text and identifiers, not media. Editing/canceling invalidates results but cannot recall a dispatched provider request. Approval records a user decision; the server cannot cryptographically prove arbitrary client pixels were redacted, so revision validation works with the app's local rendering/upload path.

## Separate disclosures

Typed notes/context are stored online and may inform model requests. Explicit voice notes go to ElevenLabs for transcription; TTS sends actual assistant text. Covers do not redact speech. No system audio is recorded. Existing recordings start unreviewed, but review cannot undo earlier disclosures.

There are no accounts or cloud media backups. Signed guest cookies isolate text under the seven-day policy. Deleting/forgetting evidence invalidates derived knowledge and removes affected local media after confirmation.
