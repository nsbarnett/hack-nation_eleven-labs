import { useEffect, useRef, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { useApp, useMedia, run } from "../stores";
import { Button, Empty } from "../components/Controls";
import {
  readAsset,
  readReview,
  removeAssets,
  listAssets,
} from "../web/localMedia";
import {
  analyzeReview,
  approveReview,
  cancelPrivacyJob,
  editReview,
  getReview,
  renderReview,
  scanReview,
  usePrivacyJobs,
} from "../privacy/service";
import { normalizeRect, rectAt } from "../privacy/geometry";
import {
  uid,
  type Cover,
  type Marker,
  type Rect,
  type Review,
} from "../privacy/types";

export function PrivacyReview() {
  const data = useApp((s) => s.data),
    recording = useMedia((s) => s.status.state),
    job = usePrivacyJobs();
  const [draft, setDraft] = useState<Review>(),
    [segmentIndex, setSegmentIndex] = useState(0),
    [time, setTime] = useState(0);
  const [selected, setSelected] = useState(""),
    [source, setSource] = useState(""),
    [preview, setPreview] = useState(false);
  const [draw, setDraw] = useState(false),
    [temporary, setTemporary] = useState<Rect>(),
    [acknowledged, setAcknowledged] = useState(false),
    [saving, setSaving] = useState(false);
  const video = useRef<HTMLVideoElement>(null),
    stage = useRef<SVGSVGElement>(null);
  const gesture = useRef<{
    x: number;
    y: number;
    mode: string;
    rect?: Rect;
  } | null>(null);
  const guest = data?.guest,
    session = data?.session,
    busy = !!job.label || saving || recording !== "idle";
  const segment = draft?.segments[segmentIndex],
    cover = draft?.covers.find((c) => c.id === selected);
  useEffect(() => {
    if (!guest || !session) return;
    let alive = true;
    const load = () => {
      void readReview(guest, session.id).then((r) => {
        if (alive) setDraft(r);
      });
    };
    run(async () => {
      const r = await getReview(guest, session.id, session.privacy.revision);
      if (alive) setDraft(r);
    });
    window.addEventListener("privacy-change", load);
    return () => {
      alive = false;
      window.removeEventListener("privacy-change", load);
    };
  }, [guest, session?.id, session?.privacy.revision]);
  useEffect(() => {
    setSegmentIndex(0);
    setSelected("");
    setPreview(false);
  }, [session?.id]);
  useEffect(() => {
    setAcknowledged(false);
  }, [draft?.revision]);
  useEffect(() => {
    setSource("");
    let url = "",
      alive = true;
    if (draft && segment)
      run(async () => {
        const blob = await readAsset(
          draft.guest,
          draft.session,
          preview ? draft.derivatives[segment.name] : segment.name,
        );
        url = URL.createObjectURL(blob);
        if (alive) setSource(url);
        else URL.revokeObjectURL(url);
      });
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [
    draft?.session,
    segment?.name,
    preview,
    draft?.derivatives[segment?.name || ""],
  ]);
  async function save(change: (copy: Review) => void) {
    if (!draft || busy) return;
    setSaving(true);
    try {
      const copy = structuredClone(draft);
      change(copy);
      setDraft(await editReview(copy));
      setPreview(false);
    } finally {
      setSaving(false);
    }
  }
  function seek(t: number) {
    if (!segment) return;
    const value = Math.max(0, Math.min(segment.duration, t));
    if (video.current) {
      video.current.pause();
      video.current.currentTime = value;
    }
    setTime(value);
  }
  function openMarker(marker: Marker) {
    if (!draft) return;
    const index = draft.segments.findIndex((s) => s.name === marker.segment);
    setPreview(false);
    setSegmentIndex(index);
    setTime(marker.time);
    if (index === segmentIndex) seek(marker.time);
  }
  function boundary(t: number) {
    const cuts = [...(draft?.cuts[segment!.name] || [])].sort((a, b) => a - b);
    return {
      start: Math.max(0, ...cuts.filter((c) => c <= t)),
      end: Math.min(segment!.duration, ...cuts.filter((c) => c > t)),
    };
  }
  function addCover(rect: Rect, t = time, marker?: Marker) {
    if (!segment) return;
    const bounds = boundary(t),
      start = Math.max(bounds.start, t - 0.25),
      end = Math.min(bounds.end, (marker?.until ?? t) + 0.75);
    const id = uid();
    setSelected(id);
    setDraw(false);
    run(() =>
      save((d) => {
        d.covers.push({
          id,
          segment: segment.name,
          start,
          end: Math.max(start + 0.01, end),
          keyframes: [{ time: start, rect: normalizeRect(rect) }],
        });
        if (marker)
          d.markers.find((m) => m.id === marker.id)!.decision = "covered";
      }),
    );
  }
  function place(rect: Rect) {
    if (!cover) {
      addCover(rect);
      return;
    }
    run(() =>
      save((d) => {
        const target = d.covers.find((c) => c.id === cover.id)!;
        const at = Math.max(target.start, Math.min(target.end, time));
        target.keyframes = [
          ...target.keyframes.filter((k) => Math.abs(k.time - at) > 0.02),
          { time: at, rect: normalizeRect(rect) },
        ].sort((a, b) => a.time - b.time);
      }),
    );
  }
  function split() {
    if (!cover || time <= cover.start || time >= cover.end) return;
    run(() =>
      save((d) => {
        const rect = rectAt(cover, time)!;
        d.covers = d.covers.filter((c) => c.id !== cover.id);
        d.covers.push(
          {
            ...cover,
            end: time,
            keyframes: [
              ...cover.keyframes.filter((k) => k.time < time),
              { time, rect },
            ],
          },
          {
            ...cover,
            id: uid(),
            start: time,
            keyframes: [
              { time, rect },
              ...cover.keyframes.filter((k) => k.time > time),
            ],
          },
        );
      }),
    );
  }
  if (!session || !draft || !segment)
    return (
      <Empty icon={<ShieldCheck size={30} />} heading="Review before sharing">
        Record a workflow first. Original video stays in this browser; screen
        analysis waits for your approval.
      </Empty>
    );
  const markers = draft.markers
    .filter((m) => m.segment === segment.name)
    .sort((a, b) => a.time - b.time);
  const currentRect = cover && rectAt(cover, time);
  const unresolved = draft.markers.filter(
    (m) => m.decision === "pending",
  ).length;
  const rendered = draft.segments.every((s) => !!draft.derivatives[s.name]);
  function point(e: React.PointerEvent) {
    const bounds = stage.current!.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1, (e.clientX - bounds.left) / bounds.width)),
      y: Math.max(0, Math.min(1, (e.clientY - bounds.top) / bounds.height)),
    };
  }
  return (
    <>
      <header className="page-heading compact">
        <span className="eyebrow">LOCAL PRIVACY REVIEW</span>
        <h1>Choose what leaves your screen.</h1>
        <p>
          {session.title} · Revision {draft.revision}
        </p>
      </header>
      <div className="notice-banner">
        <span>
          Suggestions can miss brief appearances, names, addresses, faces, or
          unreadable text. Review every segment. Covers affect pixels, not
          speech, typed notes, or information disclosed by older recordings.
        </span>
      </div>
      {recording !== "idle" && (
        <p role="status">Stop recording to edit and approve privacy.</p>
      )}
      <section className="panel review-tools">
        <Button disabled={busy} onClick={() => run(() => scanReview(draft))}>
          {draft.scan === "complete"
            ? "Scan again locally"
            : "Scan recording locally"}
        </Button>
        <span>
          {draft.scanned} frames checked · {draft.scan} · {unresolved}{" "}
          unresolved suggestions
        </span>
        {job.label && (
          <>
            <progress aria-label={job.label} max={1} value={job.progress} />
            <span role="status">
              {job.label} · {Math.round(job.progress * 100)}%
            </span>
            <Button onClick={cancelPrivacyJob}>Cancel processing</Button>
          </>
        )}
      </section>
      {!!draft.gaps.length && (
        <div className="error-banner" role="status">
          Coverage gaps: {[...new Set(draft.gaps)].join(" ")}
        </div>
      )}
      <div className="privacy-layout">
        <section className="panel privacy-player">
          <div className="review-tools">
            <label>
              Segment{" "}
              <select
                aria-label="Recording segment"
                value={segmentIndex}
                onChange={(e) => {
                  setSegmentIndex(Number(e.target.value));
                  setTime(0);
                  setSelected("");
                }}
              >
                {draft.segments.map((s, i) => (
                  <option key={s.name} value={i}>
                    {i + 1} · {s.duration.toFixed(1)}s
                  </option>
                ))}
              </select>
            </label>
            <strong>
              {preview
                ? "Rendered copy — covers are permanent"
                : "Original — may contain sensitive information"}
            </strong>
            {rendered && (
              <Button onClick={() => setPreview(!preview)}>
                {preview ? "Edit original" : "Preview rendered copy"}
              </Button>
            )}
          </div>
          <div className={`review-stage ${draw ? "drawing" : ""}`}>
            {source && (
              <video
                ref={video}
                src={source}
                controls={preview}
                playsInline
                onLoadedMetadata={() => {
                  if (video.current) video.current.currentTime = time;
                }}
                onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
              />
            )}
            {!preview && (
              <svg
                ref={stage}
                className="cover-editor"
                viewBox="0 0 1000 1000"
                preserveAspectRatio="none"
                style={{ pointerEvents: draw || !!selected ? "auto" : "none" }}
                aria-label="Draw, move or resize a cover"
                onPointerDown={(e) => {
                  if (busy) return;
                  const p = point(e);
                  video.current?.pause();
                  const mode =
                    (e.target as SVGElement).dataset.mode ||
                    (draw ? "draw" : "");
                  if (!mode) return;
                  gesture.current = {
                    ...p,
                    mode,
                    rect: currentRect || undefined,
                  };
                  e.currentTarget.setPointerCapture(e.pointerId);
                }}
                onPointerMove={(e) => {
                  const g = gesture.current;
                  if (!g) return;
                  const p = point(e);
                  if (g.mode === "draw")
                    setTemporary({
                      x: Math.min(p.x, g.x),
                      y: Math.min(p.y, g.y),
                      width: Math.abs(p.x - g.x),
                      height: Math.abs(p.y - g.y),
                    });
                  else if (g.rect)
                    setTemporary(
                      normalizeRect(
                        g.mode === "move"
                          ? {
                              ...g.rect,
                              x: g.rect.x + p.x - g.x,
                              y: g.rect.y + p.y - g.y,
                            }
                          : {
                              ...g.rect,
                              width: Math.max(0.005, p.x - g.rect.x),
                              height: Math.max(0.005, p.y - g.rect.y),
                            },
                      ),
                    );
                }}
                onPointerUp={() => {
                  const g = gesture.current;
                  gesture.current = null;
                  if (
                    temporary &&
                    temporary.width > 0.003 &&
                    temporary.height > 0.003
                  ) {
                    if (g?.mode === "draw") addCover(temporary);
                    else place(temporary);
                  }
                  setTemporary(undefined);
                }}
                onPointerCancel={() => {
                  gesture.current = null;
                  setTemporary(undefined);
                }}
              >
                {draft.covers
                  .filter((c) => c.segment === segment.name)
                  .map((c) => {
                    const r =
                      c.id === selected && temporary
                        ? temporary
                        : rectAt(c, time);
                    return (
                      r && (
                        <g key={c.id}>
                          <rect
                            data-mode="move"
                            x={r.x * 1000}
                            y={r.y * 1000}
                            width={r.width * 1000}
                            height={r.height * 1000}
                            fill="#111"
                            stroke={c.id === selected ? "#5b9bea" : "white"}
                            strokeWidth={3}
                            onClick={() => setSelected(c.id)}
                          />
                          {c.id === selected && (
                            <rect
                              data-mode="resize"
                              x={(r.x + r.width) * 1000 - 9}
                              y={(r.y + r.height) * 1000 - 9}
                              width={18}
                              height={18}
                              fill="white"
                              stroke="#5b9bea"
                            />
                          )}
                        </g>
                      )
                    );
                  })}
                {draw && temporary && (
                  <rect
                    x={temporary.x * 1000}
                    y={temporary.y * 1000}
                    width={temporary.width * 1000}
                    height={temporary.height * 1000}
                    fill="#111"
                    opacity={0.8}
                  />
                )}
              </svg>
            )}
          </div>
          <div className="review-timeline">
            <input
              type="range"
              min={0}
              max={segment.duration || 0.1}
              step={1 / 30}
              value={time}
              aria-label="Review time"
              onChange={(e) => seek(Number(e.target.value))}
            />
            {markers.map((m) => (
              <button
                key={m.id}
                style={{ left: `${(100 * m.time) / (segment.duration || 1)}%` }}
                title={`${m.category} at ${m.time.toFixed(2)}s`}
                aria-label={`${m.category} at ${m.time.toFixed(2)} seconds`}
                onClick={() => openMarker(m)}
              />
            ))}
          </div>
          <div className="review-tools">
            <Button
              onClick={() => {
                if (video.current?.paused) void video.current.play();
                else video.current?.pause();
              }}
            >
              Play / pause
            </Button>
            <Button
              onClick={() => {
                const m = markers.filter((m) => m.time < time - 0.01).at(-1);
                if (m) openMarker(m);
              }}
            >
              Previous finding
            </Button>
            <Button onClick={() => seek(time - 1 / 15)}>−1 frame</Button>
            <span>{time.toFixed(2)}s</span>
            <Button onClick={() => seek(time + 1 / 15)}>+1 frame</Button>
            <Button
              onClick={() => {
                const m = markers.find((m) => m.time > time + 0.01);
                if (m) openMarker(m);
              }}
            >
              Next finding
            </Button>
          </div>
          <div className="review-tools">
            <Button
              disabled={busy || preview}
              onClick={() => {
                setDraw(!draw);
                setSelected("");
              }}
            >
              {draw ? "Cancel drawing" : "Draw a cover"}
            </Button>
            <Button
              disabled={busy}
              onClick={() =>
                run(() =>
                  save((d) => {
                    d.markers.push({
                      id: uid(),
                      segment: segment.name,
                      time,
                      category: "Manual review marker",
                      decision: "pending",
                    });
                  }),
                )
              }
            >
              Add marker here
            </Button>
          </div>
          <p className="small muted">
            Draw over the image, then edit the interval below. Frame steps use
            the capture rate of 15 fps. Suggested cuts:{" "}
            {(draft.cuts[segment.name] || []).map((t) => (
              <button className="text-button" key={t} onClick={() => seek(t)}>
                {t.toFixed(2)}s{" "}
              </button>
            ))}
          </p>
        </section>
        <aside className="panel review-findings">
          <h3>Suggestions to review</h3>
          {!markers.length && (
            <p className="muted">
              No suggestions in this segment. This is not a guarantee that it
              contains no sensitive information.
            </p>
          )}
          {markers.map((m) => (
            <div className="finding" key={m.id}>
              <button className="text-button" onClick={() => openMarker(m)}>
                {m.time.toFixed(2)}s · {m.category}
              </button>
              <span className="small muted">{m.decision}</span>
              <div className="review-tools">
                <Button
                  disabled={busy || !m.rect || m.segment !== segment.name}
                  onClick={() => {
                    openMarker(m);
                    addCover(m.rect!, m.time, m);
                  }}
                >
                  Cover
                </Button>
                {!m.rect && (
                  <Button
                    disabled={
                      busy ||
                      !draft.covers.some(
                        (c) => c.segment === m.segment && !!rectAt(c, m.time),
                      )
                    }
                    onClick={() =>
                      run(() =>
                        save((d) => {
                          d.markers.find((x) => x.id === m.id)!.decision =
                            "covered";
                        }),
                      )
                    }
                  >
                    Use drawn cover
                  </Button>
                )}
                <Button
                  disabled={busy}
                  onClick={() =>
                    run(() =>
                      save((d) => {
                        d.markers.find((x) => x.id === m.id)!.decision =
                          m.decision === "dismissed" ? "pending" : "dismissed";
                      }),
                    )
                  }
                >
                  {m.decision === "dismissed" ? "Reopen" : "Dismiss"}
                </Button>
              </div>
            </div>
          ))}
        </aside>
      </div>
      <section className="panel review-tools">
        <label>
          Cover{" "}
          <select
            aria-label="Selected cover"
            value={selected}
            onChange={(e) => {
              setSelected(e.target.value);
              const c = draft.covers.find((c) => c.id === e.target.value);
              if (c) {
                setSegmentIndex(
                  draft.segments.findIndex((s) => s.name === c.segment),
                );
                seek(c.start);
              }
            }}
          >
            <option value="">Select a cover</option>
            {draft.covers.map((c, i) => (
              <option key={c.id} value={c.id}>
                {i + 1} · {c.start.toFixed(2)}–{c.end.toFixed(2)}s
              </option>
            ))}
          </select>
        </label>
        {cover && (
          <>
            {(["start", "end"] as const).map((field) => (
              <label key={field}>
                {field} (seconds)
                <input
                  key={`${cover.id}-${cover[field]}`}
                  aria-label={`Cover ${field}`}
                  type="number"
                  min={0}
                  max={segment.duration}
                  step={0.01}
                  defaultValue={cover[field].toFixed(2)}
                  disabled={busy}
                  onBlur={(e) => {
                    const value = Number(e.target.value);
                    if (value === cover[field]) return;
                    run(() =>
                      save((d) => {
                        const c = d.covers.find((c) => c.id === cover.id)!;
                        c[field] = value;
                        const r = rectAt(cover, cover.start)!;
                        c.keyframes = c.keyframes.filter(
                          (k) => k.time >= c.start && k.time <= c.end,
                        );
                        if (!c.keyframes.length)
                          c.keyframes = [{ time: c.start, rect: r }];
                      }),
                    );
                  }}
                />
              </label>
            ))}
            <Button
              disabled={busy || !currentRect}
              onClick={() => place(currentRect!)}
            >
              Add position keyframe here
            </Button>
            <Button
              disabled={busy || time <= cover.start || time >= cover.end}
              onClick={split}
            >
              Split at playhead
            </Button>
            <Button
              disabled={busy}
              onClick={() =>
                run(() =>
                  save((d) => {
                    d.covers = d.covers.filter((c) => c.id !== cover.id);
                    d.markers.forEach((m) => {
                      if (m.decision === "covered") m.decision = "pending";
                    });
                    setSelected("");
                  }),
                )
              }
            >
              Remove cover
            </Button>
            <p className="small muted full">
              Move or resize the selected box at another time to add a position
              keyframe. Split at each screen cut; covers cannot cross detected
              cuts.
            </p>
            {cover.keyframes.map((k) => (
              <Button key={k.time} onClick={() => seek(k.time)}>
                Keyframe {k.time.toFixed(2)}s
              </Button>
            ))}
            {currentRect &&
              (["x", "y", "width", "height"] as const).map((field) => (
                <label key={field}>
                  {field} (%)
                  <input
                    key={`${cover.id}-${field}-${currentRect[field]}`}
                    aria-label={`Cover ${field} percent`}
                    type="number"
                    min={0}
                    max={100}
                    step={0.1}
                    defaultValue={(currentRect[field] * 100).toFixed(1)}
                    disabled={busy}
                    onBlur={(e) => {
                      const value = Number(e.target.value) / 100;
                      if (Math.abs(value - currentRect[field]) > 0.001)
                        place({ ...currentRect, [field]: value });
                    }}
                  />
                </label>
              ))}
          </>
        )}
      </section>
      <section className="panel privacy-approve">
        <h3>Render, review, then approve</h3>
        <p>
          Rendering creates a separate WebM with opaque covers baked in. Your
          originals remain here. Only approved rendered frames can be sent for
          screen analysis.
        </p>
        <div className="review-tools">
          <Button
            disabled={busy || unresolved > 0 || draft.status === "approved"}
            onClick={() =>
              run(async () => {
                setDraft(await renderReview(draft));
                setPreview(true);
              })
            }
          >
            Render redacted copy
          </Button>
          <label>
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(e) => setAcknowledged(e.target.checked)}
            />{" "}
            I reviewed all segments, including any scan gaps, and approve this
            revision.
          </label>
          <Button
            disabled={
              busy ||
              !rendered ||
              !acknowledged ||
              unresolved > 0 ||
              draft.status === "approved"
            }
            onClick={() =>
              run(async () => setDraft(await approveReview(draft)))
            }
          >
            Approve reviewed recording
          </Button>
          <Button
            className="primary"
            disabled={
              busy ||
              draft.status !== "approved" ||
              !data.credentials.openai
            }
            onClick={() => run(() => analyzeReview(draft))}
          >
            Analyze approved frames
          </Button>
        </div>
        {!data?.credentials.openai && (
          <p className="small muted">
            AI is temporarily unavailable. Contact the app owner; local review and your saved recording remain available.
          </p>
        )}
        <p role="status">
          {draft.status === "approved"
            ? "Approved. Library playback and downloads use the redacted copy."
            : "Not approved. No screen frames will be shared with AI."}
        </p>
        <Button
          disabled={busy || draft.status !== "approved"}
          onClick={() =>
            run(async () => {
              if (
                !confirm(
                  "Permanently delete original video and screenshots from this browser? You will keep the approved redacted copy, but cannot revise the original afterward.",
                )
              )
                return;
              const assets = await listAssets(draft.guest, draft.session);
              await removeAssets(
                draft.guest,
                draft.session,
                new Set(
                  assets
                    .filter((a) => a.purpose !== "redacted")
                    .map((a) => a.name),
                ),
              );
              useApp.getState().go("Library");
            })
          }
        >
          Delete originals…
        </Button>
      </section>
    </>
  );
}
