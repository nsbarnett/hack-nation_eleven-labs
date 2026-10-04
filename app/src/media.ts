/** Persistent renderer service, independent of page/component lifetimes.
 * Video bytes go directly to Electron with backpressure. Only status enters React.
 */
import { useApp, useMedia, report } from "./stores";
import type { Source } from "./types";
let recorder: MediaRecorder | null = null,
  stream: MediaStream | null = null,
  video: HTMLVideoElement | null = null;
let segment = "",
  queue = Promise.resolve(),
  queued = 0,
  frameBusy = false,
  stopping = false,
  failure = false;
let timer: ReturnType<typeof setInterval> | undefined,
  sample: ReturnType<typeof setInterval> | undefined;
let started = 0,
  accumulated = 0,
  source: Source | null = null;
let microphone: MediaRecorder | null = null,
  micStream: MediaStream | null = null,
  audio: HTMLAudioElement | null = null;
let voiceGeneration = 0,
  micTimer: ReturnType<typeof setTimeout> | undefined;
let finishing: Promise<void> | null = null;
let finishResolve: (() => void) | null = null;
function status(
  patch: Partial<ReturnType<typeof useMedia.getState>["status"]>,
) {
  const value = { ...useMedia.getState().status, ...patch };
  useMedia.setState({ status: value });
  void window.desktop.status(value).catch(report);
}
export function elapsed() {
  return (
    accumulated +
    (recorder?.state === "recording" ? (performance.now() - started) / 1000 : 0)
  );
}
export function cancelVoice() {
  voiceGeneration++;
  clearTimeout(micTimer);
  if (microphone?.state === "recording") microphone.stop();
  microphone = null;
  micStream?.getTracks().forEach((t) => t.stop());
  micStream = null;
  if (audio) {
    audio.pause();
    URL.revokeObjectURL(audio.src);
    audio = null;
  }
  status({ voice: "idle" });
}
export function toggleMute() {
  cancelVoice();
  status({ muted: !useMedia.getState().status.muted });
}
export async function speak(text: string) {
  if (useMedia.getState().status.muted) return;
  cancelVoice();
  const generation = voiceGeneration;
  status({ voice: "thinking" });
  try {
    const bytes = await window.desktop.speech(text);
    if (generation !== voiceGeneration) return;
    audio = new Audio(
      URL.createObjectURL(
        new Blob([new Uint8Array(bytes)], { type: "audio/mpeg" }),
      ),
    );
    status({ voice: "speaking" });
    audio.onended = () => cancelVoice();
    await audio.play();
  } catch (error) {
    if (generation !== voiceGeneration) return;
    cancelVoice();
    report(error);
  }
}
export async function voiceNote() {
  if (!useApp.getState().data?.session)
    throw new Error("Create or open a workflow before adding a voice note.");
  if (microphone?.state === "recording") {
    microphone.stop();
    return;
  }
  if (useMedia.getState().status.state === "paused")
    throw new Error("Resume before recording an answer.");
  if (!useApp.getState().data?.credentials.elevenlabs)
    throw new Error("Add an ElevenLabs key in Settings first.");
  cancelVoice();
  const generation = voiceGeneration;
  const capturedStream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true },
    video: false,
  });
  if (generation !== voiceGeneration) {
    capturedStream.getTracks().forEach((t) => t.stop());
    return;
  }
  const chunks: Blob[] = [];
  micStream = capturedStream;
  microphone = new MediaRecorder(micStream);
  microphone.ondataavailable = (e) => {
    if (e.data.size) chunks.push(e.data);
  };
  microphone.onstop = async () => {
    capturedStream.getTracks().forEach((t) => t.stop());
    if (generation !== voiceGeneration) return;
    clearTimeout(micTimer);
    microphone = null;
    micStream = null;
    status({ voice: "thinking" });
    try {
      const bytes = new Uint8Array(await new Blob(chunks).arrayBuffer());
      const answer = await window.desktop.transcribe(bytes);
      if (generation !== voiceGeneration) return;
      if (answer.text)
        await useApp.getState().command("note", {
          kind: useApp.getState().data?.question ? "answer" : "note",
          text: answer.text,
        });
      else
        throw new Error(
          "No speech was transcribed. Try again or type your answer.",
        );
    } catch (error) {
      report(error);
    } finally {
      if (generation === voiceGeneration) status({ voice: "idle" });
    }
  };
  microphone.start();
  status({ voice: "listening" });
  micTimer = setTimeout(() => {
    if (microphone?.state === "recording") microphone.stop();
  }, 30000);
}
async function sendFrame() {
  if (frameBusy || !video || !stream || !video.videoWidth || stopping) return;
  frameBusy = true;
  try {
    const canvas = document.createElement("canvas");
    const scale = Math.min(1, 1280 / video.videoWidth);
    canvas.width = video.videoWidth * scale;
    canvas.height = video.videoHeight * scale;
    canvas
      .getContext("2d")!
      .drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", 0.75),
    );
    if (blob && !stopping)
      await window.desktop.frame(
        new Uint8Array(await blob.arrayBuffer()),
        elapsed(),
      );
  } catch (error) {
    report(error);
  } finally {
    frameBusy = false;
  }
}
export async function startRecording(selected?: Source) {
  if (recorder || stopping) return;
  const current = useApp.getState().data?.session;
  if (!current) throw new Error("Create a workflow first.");
  if (selected) source = selected;
  if (!source) throw new Error("Choose a screen or window.");
  if (useMedia.getState().status.state === "idle")
    accumulated = current.duration;
  await window.desktop.selectSource(source.id);
  stream = await navigator.mediaDevices.getDisplayMedia({
    video: { frameRate: 15 },
    audio: false,
  });
  failure = false;
  queue = Promise.resolve();
  queued = 0;
  try {
    segment = await window.desktop.beginSegment();
    const mime = [
      "video/webm;codecs=vp9",
      "video/webm;codecs=vp8",
      "video/webm",
    ].find(MediaRecorder.isTypeSupported);
    recorder = new MediaRecorder(stream, {
      mimeType: mime,
      videoBitsPerSecond: 2_000_000,
    });
    recorder.ondataavailable = (e) => {
      if (!e.data.size) return;
      queued += e.data.size;
      if (queued > 32 * 1024 * 1024) {
        failure = true;
        report(new Error("Recording stopped: disk writes could not keep up."));
        void stopRecording();
      }
      queue = queue
        .then(async () => {
          await window.desktop.chunk(
            segment,
            new Uint8Array(await e.data.arrayBuffer()),
          );
          queued -= e.data.size;
        })
        .catch((error) => {
          failure = true;
          report(error);
          void stopRecording();
        });
    };
    recorder.onerror = () => {
      failure = true;
      report(
        new Error(
          "Recording failed. The completed video chunks have been retained.",
        ),
      );
      void stopRecording();
    };
    stream.getVideoTracks()[0].onended = () => {
      void stopRecording();
    };
    video = document.createElement("video");
    video.muted = true;
    video.srcObject = stream;
    await video.play();
    await useApp
      .getState()
      .command("recording", { state: "recording", duration: accumulated });
    started = performance.now();
    recorder.start(1000);
    useMedia.setState({
      stream,
      sourceName: source.name,
      safePreview: source.id.startsWith("window:"),
    });
    status({ state: "recording", duration: elapsed() });
    timer = setInterval(() => status({ duration: elapsed() }), 1000);
    sample = setInterval(() => void sendFrame(), 2000);
  } catch (error) {
    stream?.getTracks().forEach((t) => t.stop());
    stream = null;
    recorder = null;
    if (segment) await window.desktop.endSegment(segment).catch(() => {});
    throw error;
  }
}
export async function stopRecording(paused = false) {
  if (stopping) return finishing;
  stopping = true;
  finishing = new Promise<void>((resolve) => {
    finishResolve = resolve;
  });
  cancelVoice();
  clearInterval(timer);
  clearInterval(sample);
  accumulated = elapsed();
  try {
    // Stop tracks immediately for privacy; still flush the recorder's final chunk.
    if (recorder && recorder.state !== "inactive") {
      const stopped = new Promise<void>((resolve) =>
        recorder!.addEventListener("stop", () => resolve(), { once: true }),
      );
      recorder.stop();
      stream?.getTracks().forEach((t) => t.stop());
      await stopped;
    } else stream?.getTracks().forEach((t) => t.stop());
    await queue;
    if (segment) await window.desktop.endSegment(segment);
    await useApp.getState().command("recording", {
      state: paused && !failure ? "paused" : "idle",
      duration: accumulated,
    });
  } catch (error) {
    report(error);
  } finally {
    recorder = null;
    stream = null;
    video = null;
    segment = "";
    stopping = false;
    finishResolve?.();
    finishing = null;
    finishResolve = null;
    useMedia.setState({ stream: null });
    status({
      state: paused && !failure ? "paused" : "idle",
      duration: accumulated,
    });
  }
}
export function canResume() {
  return !!source;
}
