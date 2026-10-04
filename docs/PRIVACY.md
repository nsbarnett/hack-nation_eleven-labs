# Local review and timed redaction

Browser capture and disclosure are separate. AI is available without activation switches. Screen upload still requires explicit approval of the local rendered recording at the current privacy revision and the Analyze action. Optional live reviewer interjections use typed/voice notes only.

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

The browser scans the approved derivative locally at one-second intervals, scores the largest RGB change in a 16-pixel tile of a 320-pixel-wide thumbnail, and prefers before/after pairs for changes >=0.06 followed by a stable sample <=0.02 (the final sample is also eligible). It retains first/last frames where capacity permits and fills spare capacity with periodic samples. The original upload allowance, the sum of max(1, ceil(segment duration/10)), is retained and capped at 30 per workflow. A single clip of ten seconds or less has only one frame of capacity, so a comparison may remain unsupported. These are tuning heuristics, not proof of meaningful actions. The observer must still establish readable events. Selection is persisted per privacy revision; partially uploaded older reviews finish their fixed-interval selection without adding a second batch. Each model job must finish successfully before its frame counts as analyzed. The service holds at most three frames in memory; PostgreSQL stores text and identifiers, not media. Editing/canceling invalidates results but cannot recall a dispatched provider request. Approval records a user decision; the server cannot cryptographically prove arbitrary client pixels were redacted, so revision validation works with the app's local rendering/upload path.

## Separate disclosures

Typed notes/context are stored online and may inform model requests. Explicit voice notes go to ElevenLabs for transcription; TTS sends actual assistant text. Covers do not redact speech. No system audio is recorded. Existing recordings start unreviewed, but review cannot undo earlier disclosures.

There are no accounts or cloud media backups. Signed guest cookies isolate text under the seven-day policy. Deleting/forgetting evidence invalidates derived knowledge and removes affected local media after confirmation.

## Workflow deletion (0.5.0)

Delete appears on each workflow card and in Settings. A dialog names the workflow and requires a Delete workflow button; no phrase is typed. The guest-scoped API accepts an explicit target ID and confirmed=true. Other open workflows remain active. Capture must stop before deleting its own workflow. Target workers are canceled and local writes drained before deleting hosted data and browser assets, chunks and privacy drafts. A pending cleanup marker supports retries and reload recovery if local cleanup fails after server deletion.
