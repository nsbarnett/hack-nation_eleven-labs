/** Persistent local jobs outlive page navigation. Originals never leave this module. */
import { create } from "zustand";
import { useApp } from "../stores";
import {
  appendAsset,
  beginAsset,
  finishAsset,
  listAssets,
  readAsset,
  readReview,
  removeAssets,
  writeReview,
} from "../web/localMedia";
import {
  newReview,
  uid,
  type Review,
  type Marker,
  type Segment,
} from "./types";
import { validateCovers } from "./geometry";
import { selectAnalysisFrames, type Sample } from "./selection";

export const usePrivacyJobs = create<{
  session: string;
  label: string;
  progress: number;
}>(() => ({ session: "", label: "", progress: 0 }));
const workers = new Set<Worker>();
const workerOwners = new WeakMap<Worker, string>();
let active: { session: string; cancelled: boolean } | undefined;
const serial = new Map<string, Promise<unknown>>();
const deleting = new Set<string>();
function local(
  guest: string,
  session: string,
  mutate: (draft: Review) => void | Promise<void>,
) {
  const key = guest + session;
  const next = (serial.get(key) || Promise.resolve())
    .catch(() => {})
    .then(async () => {
      if (deleting.has(session)) throw new DOMException("Workflow deletion is in progress.", "AbortError");
      const draft =
        (await readReview(guest, session)) || newReview(guest, session);
      await mutate(draft);
      await writeReview(draft);
      window.dispatchEvent(
        new CustomEvent("privacy-change", { detail: session }),
      );
      return draft;
    });
  serial.set(key, next);
  return next;
}
export async function prepareWorkflowDeletion(guest: string, session: string) {
  deleting.add(session);
  const stopWorkers = () => workers.forEach((worker) => {
    if (workerOwners.get(worker) === session) worker.dispatchEvent(new Event("cancel"));
  });
  if (active?.session === session) {
    active.cancelled = true;
    const finished = new Promise<void>((resolve) => {
      const unsubscribe = usePrivacyJobs.subscribe((state) => {
        if (state.session !== session) { unsubscribe(); resolve(); }
      });
    });
    stopWorkers();
    await finished;
  }
  stopWorkers();
  await serial.get(guest + session)?.catch(() => {});
}
export function finishWorkflowDeletion(session: string) {
  deleting.delete(session);
}
function job(
  data: unknown,
  update: (event: any) => void | Promise<void> = () => {},
) {
  return new Promise<any>((resolve, reject) => {
    const worker = new Worker(
      new URL("./processor.worker.ts", import.meta.url),
      { type: "module" },
    );
    workers.add(worker);
    workerOwners.set(worker, data && typeof data === "object" && "session" in data ? String(data.session) : active?.session || "");
    let events = Promise.resolve();
    const close = () => {
      workers.delete(worker);
      worker.terminate();
    };
    // A cancel event rejects the promise as well as stopping the worker.
    const cancel = () => {
      close();
      if (deleting.has(workerOwners.get(worker) || "")) {
        reject(new DOMException("Workflow processing stopped for deletion.", "AbortError"));
        return;
      }
      reject(
        new Error(
          "Local processing canceled. Original media and edits are retained.",
        ),
      );
    };
    worker.addEventListener("cancel", cancel);
    worker.onerror = () => {
      close();
      reject(
        new Error(
          "Local processor failed to load. Reload the app and check that OCR assets are installed.",
        ),
      );
    };
    worker.onmessage = ({ data: event }) => {
      events = events
        .then(async () => {
          if (event.type === "error") {
            close();
            reject(new Error(event.message));
          } else if (event.type === "done" || event.type === "detected") {
            close();
            resolve(event);
          } else await update(event);
        })
        .catch((error) => {
          close();
          reject(error);
        });
    };
    worker.postMessage(data);
  });
}
export function cancelPrivacyJob() {
  if (active) active.cancelled = true;
  workers.forEach((worker) => worker.dispatchEvent(new Event("cancel")));
  const data = useApp.getState().data;
  if (
    (usePrivacyJobs.getState().label === "Analyzing approved frames" || usePrivacyJobs.getState().label.startsWith("Evaluating context")) &&
    data?.session &&
    data.guest
  ) {
    void useApp
      .getState()
      .command("privacy-reset", { revision: data.session.privacy.revision })
      .then((privacy) =>
        local(data.guest!, data.session!.id, (draft) => {
          draft.revision = privacy.revision;
          draft.status = "draft";
          draft.uploaded = [];
          draft.selection = undefined;
          draft.derivatives = {};
        }),
      )
      .catch((error) => useApp.getState().fail(error));
  }
}
function startJob(session: string, label: string) {
  if (active)
    throw new Error("Finish or cancel the current privacy task first.");
  active = { session, cancelled: false };
  usePrivacyJobs.setState({ session, label, progress: 0 });
  return active;
}
function finishJob() {
  active = undefined;
  usePrivacyJobs.setState({ session: "", label: "", progress: 0 });
}

/** Import old browser media as unreviewed, without changing or deleting originals. */
export async function getReview(
  guest: string,
  session: string,
  revision: number,
) {
  return local(guest, session, async (draft) => {
    const assets = (await listAssets(guest, session)).filter(
      (a) =>
        (a.purpose || "source") === "source" &&
        a.type.startsWith("video/") &&
        a.size,
    );
    let start = 0;
    draft.segments = assets
      .sort((a, b) => (a.start ?? 0) - (b.start ?? 0))
      .map((a) => {
        const prior = draft.segments.find((s) => s.name === a.name);
        const segment = {
          name: a.name,
          start: a.start ?? prior?.start ?? start,
          duration: prior?.duration || a.duration || 0,
          width: prior?.width || a.width || 0,
          height: prior?.height || a.height || 0,
        };
        start = segment.start + segment.duration;
        return segment;
      });
    if (draft.revision !== revision) {
      draft.revision = revision;
      draft.status = "draft";
      draft.derivatives = {};
      draft.uploaded = [];
      draft.selection = undefined;
    }
    if (draft.status === "rendering" && !active) draft.status = "draft";
    if (draft.scan === "scanning" && !active) {
      draft.scan = "incomplete";
      draft.gaps.push(
        "The previous scan was interrupted. Run the scan again or review every segment manually.",
      );
    }
  });
}
function addFindings(
  draft: Review,
  segment: string,
  time: number,
  findings: Omit<Marker, "id" | "segment" | "time" | "decision">[],
) {
  for (const f of findings) {
    const repeated = draft.markers.find(
      (m) =>
        m.segment === segment &&
        m.category === f.category &&
        Math.abs(time - (m.until ?? m.time)) < 1.1 &&
        m.rect &&
        f.rect &&
        Math.abs(m.rect.x - f.rect.x) + Math.abs(m.rect.y - f.rect.y) < 0.04,
    );
    if (repeated) {
      repeated.until = Math.max(time, repeated.until ?? repeated.time);
      continue;
    }
    draft.markers.push({ ...f, id: uid(), segment, time, decision: "pending" });
  }
}
let detecting = false;
export async function detectLive(
  guest: string,
  session: string,
  segment: string,
  time: number,
  blob: Blob,
) {
  if (detecting || active) return; // Bounded: skip rather than queue raw frames.
  detecting = true;
  try {
    const result = await job({ op: "detect", blob, session });
    if (deleting.has(session)) return;
    await local(guest, session, (draft) =>
      addFindings(draft, segment, time, result.findings),
    );
  } catch {
    if (deleting.has(session)) return;
    await local(guest, session, (draft) => {
      if (
        !draft.gaps.includes(
          "Live OCR was unavailable; run a post-recording scan.",
        )
      )
        draft.gaps.push("Live OCR was unavailable; run a post-recording scan.");
    });
  } finally {
    detecting = false;
  }
}
export async function editReview(draft: Review) {
  if (active)
    throw new Error("Finish or cancel processing before editing the review.");
  const state = useApp.getState().data;
  if (state?.session?.id !== draft.session || state.recording !== "idle")
    throw new Error("Stop recording and open this workflow before editing.");
  // Invalidate on every committed edit, including after approval. The backend
  // generation token rejects in-flight model responses from older pixels.
  const privacy = await useApp
    .getState()
    .command("privacy-reset", { revision: draft.revision });
  draft.revision = privacy.revision;
  draft.status = "draft";
  draft.uploaded = [];
  draft.selection = undefined;
  const assets = await listAssets(draft.guest, draft.session);
  await removeAssets(
    draft.guest,
    draft.session,
    new Set(assets.filter((a) => a.purpose === "redacted").map((a) => a.name)),
  );
  draft.derivatives = {};
  return local(draft.guest, draft.session, (stored) => {
    Object.assign(stored, draft);
  });
}
export async function scanReview(draft: Review) {
  // Re-scanning an approved recording is an edit; no old approval survives.
  draft = await editReview(draft);
  const token = startJob(draft.session, "Scanning locally");
  try {
    const partial = (await listAssets(draft.guest, draft.session)).some(
      (a) =>
        a.type.startsWith("video/") && a.purpose !== "redacted" && a.partial,
    );
    draft = await local(draft.guest, draft.session, (d) => {
      d.scan = "scanning";
      d.scanned = 0;
      d.expected = d.segments.reduce(
        (n, s) => n + Math.ceil(s.duration * 2),
        0,
      );
      d.gaps = partial
        ? [
            "A recording was interrupted; its final frames may be missing. Review the retained segments manually.",
          ]
        : [];
    });
    for (let index = 0; index < draft.segments.length; index++) {
      if (token.cancelled)
        throw new Error("Scan canceled. Unscanned moments need manual review.");
      const segment = draft.segments[index],
        blob = await readAsset(draft.guest, draft.session, segment.name);
      await job({ op: "scan", blob, segment }, (event) =>
        local(draft.guest, draft.session, (d) => {
          if (event.type === "metadata")
            Object.assign(d.segments[index], event.segment);
          if (
            event.type === "cut" &&
            !(d.cuts[segment.name] || []).some(
              (t) => Math.abs(t - event.time) < 0.01,
            )
          )
            (d.cuts[segment.name] ??= []).push(event.time);
          if (event.type === "gap") d.gaps.push(event.message);
          if (event.type === "findings") {
            addFindings(d, segment.name, event.time, event.findings);
            d.scanned++;
            usePrivacyJobs.setState({
              progress: (index + event.progress) / draft.segments.length,
            });
          }
        }).then(() => {}),
      );
      const updated = await readReview(draft.guest, draft.session);
      const timing = updated?.segments[index];
      if (timing && useApp.getState().data?.session?.id === draft.session)
        await useApp
          .getState()
          .command("local-segment", {
            filename: timing.name,
            start: timing.start,
            duration: timing.duration,
          });
    }
    await local(draft.guest, draft.session, (d) => {
      d.scan = d.gaps.length ? "incomplete" : "complete";
    });
  } catch (error) {
    await local(draft.guest, draft.session, (d) => {
      d.scan = "incomplete";
      d.gaps.push(String(error instanceof Error ? error.message : error));
    });
    throw error;
  } finally {
    finishJob();
  }
}
export async function renderReview(draft: Review) {
  if (draft.status === "approved")
    throw new Error(
      "Edit the review before rendering another revision. The approved copy is already available in Library.",
    );
  if (!draft.segments.length || draft.segments.some((s) => !s.duration))
    throw new Error(
      "Scan this recording first so its segment timing can be recovered.",
    );
  if (draft.markers.some((m) => m.decision === "pending"))
    throw new Error("Accept or dismiss every suggestion before rendering.");
  validateCovers(draft.covers, draft.segments, draft.cuts);
  const estimate = await navigator.storage.estimate();
  const needed =
    Math.min(
      100_000_000,
      draft.segments.reduce((n, s) => n + s.duration * 300_000, 0),
    ) + 10_000_000;
  if ((estimate.quota ?? 0) - (estimate.usage ?? 0) < needed)
    throw new Error(
      "Not enough browser storage to render safely. Free space or delete other workflows. Originals and edits are retained.",
    );
  const token = startJob(draft.session, "Rendering covers into video");
  const created: string[] = [];
  try {
    const assets = await listAssets(draft.guest, draft.session);
    await removeAssets(
      draft.guest,
      draft.session,
      new Set(
        assets.filter((a) => a.purpose === "redacted").map((a) => a.name),
      ),
    );
    await local(draft.guest, draft.session, (d) => {
      d.status = "rendering";
      d.derivatives = {};
    });
    const derivatives: Record<string, string> = {};
    for (let index = 0; index < draft.segments.length; index++) {
      if (token.cancelled) throw new Error("Rendering canceled.");
      const segment = draft.segments[index],
        name = `redacted-${uid()}.webm`;
      created.push(name);
      const blob = await readAsset(draft.guest, draft.session, segment.name);
      await job(
        {
          op: "render",
          blob,
          segment,
          name,
          guest: draft.guest,
          session: draft.session,
          revision: draft.revision,
          covers: draft.covers.filter((c) => c.segment === segment.name),
          cuts: draft.cuts[segment.name],
        },
        (event) => {
          if (event.type === "progress")
            usePrivacyJobs.setState({
              progress: (index + event.progress) / draft.segments.length,
            });
        },
      );
      derivatives[segment.name] = name;
    }
    if (token.cancelled) throw new Error("Rendering canceled.");
    return await local(draft.guest, draft.session, (d) => {
      d.status = "draft";
      d.derivatives = derivatives;
    });
  } catch (error) {
    await removeAssets(draft.guest, draft.session, new Set(created));
    await local(draft.guest, draft.session, (d) => {
      d.status = "draft";
      d.derivatives = {};
    });
    throw error;
  } finally {
    finishJob();
  }
}
export async function approveReview(draft: Review) {
  if (
    active ||
    !draft.segments.length ||
    draft.segments.some((s) => !draft.derivatives[s.name]) ||
    draft.markers.some((m) => m.decision === "pending")
  )
    throw new Error(
      "Finish rendering and resolve all suggestions before approval.",
    );
  await useApp
    .getState()
    .command("privacy-approve", { revision: draft.revision });
  return local(draft.guest, draft.session, (d) => {
    d.status = "approved";
  });
}
export async function analyzeReview(draft: Review) {
  const token = startJob(draft.session, "Preparing approved frames");
  try {
    if (draft.status !== "approved")
      throw new Error("Approve the reviewed recording before analysis.");
    let frames = draft.selection?.map((f) => ({ segment: draft.segments.find((s) => s.name === f.segment)!, time: f.time }));
    if (!frames?.length && draft.uploaded.length) {
      // Finish an older fixed-interval batch without uploading a second selection.
      frames = draft.segments.flatMap((segment) => Array.from(
        { length: Math.max(1, Math.ceil(segment.duration / 10)) },
        (_, i) => ({ segment, time: Math.min(i * 10, segment.duration - 0.01) }),
      )).slice(0, 30);
      draft = await local(draft.guest, draft.session, (d) => { d.selection = frames!.map((f) => ({ segment: f.segment.name, time: f.time })); });
    }
    if (!frames?.length) {
      const groups: { segment: Segment; samples: Sample[] }[] = [];
      for (const segment of draft.segments) {
        if (token.cancelled) throw new Error("Analysis canceled.");
        const blob = await readAsset(draft.guest, draft.session, draft.derivatives[segment.name]);
        const selected = await job({ op: "select", blob, segment }, (event) => {
          if (event.type === "progress") usePrivacyJobs.setState({ progress: (groups.length + event.progress) / draft.segments.length });
        });
        groups.push({ segment, samples: selected.samples });
      }
      frames = selectAnalysisFrames(groups);
      draft = await local(draft.guest, draft.session, (d) => { d.selection = frames!.map((f) => ({ segment: f.segment.name, time: f.time })); });
    }
    if (!frames.length) throw new Error("No approved frames are available to analyze.");
    usePrivacyJobs.setState({ label: "Analyzing approved frames", progress: 0 });
    for (let i = 0; i < frames.length; i++) {
      if (token.cancelled) throw new Error("Analysis canceled.");
      const state = await window.desktop.state();
      if (
        state.session?.id !== draft.session ||
        state.session.privacy.revision !== draft.revision ||
        state.session.privacy.status !== "approved"
      )
        throw new Error(
          "The workflow or privacy revision changed. Analysis stopped.",
        );
      if (state.busy.length) {
        await new Promise((r) => setTimeout(r, 1500));
        i--;
        continue;
      }
      const { segment, time } = frames[i],
        key = `${segment.name}:${time}`;
      if (draft.uploaded.includes(key)) { usePrivacyJobs.setState({ progress: (i + 1) / frames.length }); continue; }
      const blob = await readAsset(
        draft.guest,
        draft.session,
        draft.derivatives[segment.name],
      );
      const result = await job({ op: "frame", blob, segment, time }); // Decode the rendered copy, never the original.
      if (token.cancelled) throw new Error("Analysis canceled.");
      const id = uid(),
        filename = `${id}.jpg`,
        bytes = new Uint8Array(await result.blob.arrayBuffer());
      await beginAsset(draft.guest, draft.session, filename, "image/jpeg", {
        purpose: "redacted",
        revision: draft.revision,
        timestamp: segment.start + time,
      });
      await appendAsset(draft.guest, draft.session, filename, bytes);
      await finishAsset(draft.guest, draft.session, filename);
      await window.desktop.reviewedFrame!(
        bytes,
        segment.start + time,
        id,
        draft.session,
        draft.revision,
      );
      // A queued request is not a successful observation. Wait for the job's
      // persisted completion; provider failure leaves the frame retryable.
      const deadline = Date.now() + 90_000;
      while (true) {
        if (token.cancelled) throw new Error("Analysis canceled.");
        await new Promise((r) => setTimeout(r, 1600));
        const result = await window.desktop.state();
        if (
          result.session?.id !== draft.session ||
          result.session.privacy.revision !== draft.revision
        )
          throw new Error("Privacy revision changed.");
        if (result.session.privacy.analyzed_frames?.includes(id)) break;
        if (!result.busy.length || Date.now() > deadline)
          throw new Error(
            "Frame analysis did not complete. Check the provider error and retry; no AI result was invented.",
          );
      }
      draft = await local(draft.guest, draft.session, (d) => {
        d.uploaded.push(key);
      });
      usePrivacyJobs.setState({ progress: (i + 1) / frames.length });
      await new Promise((r) => setTimeout(r, 1600));
    }
    if (token.cancelled) throw new Error("Analysis canceled.");
    await useApp.getState().command("review-complete", { revision: draft.revision });
    const deadline = Date.now() + 90_000;
    while (true) {
      if (token.cancelled) throw new Error("Analysis canceled.");
      const state = await window.desktop.state();
      if (state.session?.id !== draft.session || state.session.privacy.revision !== draft.revision) throw new Error("The workflow or privacy revision changed.");
      if (!state.busy.length) {
        if (state.session.privacy.question_revision !== draft.revision) throw new Error("Reviewer evaluation did not finish. Retry analysis to continue.");
        break;
      }
      usePrivacyJobs.setState({ label: "Evaluating context and preparing your question", progress: 1 });
      if (Date.now() > deadline) throw new Error("Reviewer evaluation is taking longer than expected. Its status remains visible above.");
      await new Promise((r) => setTimeout(r, 1500));
    }
    await useApp.getState().refresh();
  } catch (error) {
    if (deleting.has(draft.session)) throw new DOMException("Workflow processing stopped for deletion.", "AbortError");
    throw error;
  } finally {
    finishJob();
  }
}
