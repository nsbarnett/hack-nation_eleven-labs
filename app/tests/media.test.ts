import { beforeEach, expect, test, vi } from "vitest";
import { useApp, useMedia } from "../src/stores";
import { voiceNote, cancelVoice, speak } from "../src/media";
import type { State } from "../src/types";
beforeEach(() => {
  vi.stubGlobal("window", {
    desktop: {
      status: vi.fn().mockResolvedValue(undefined),
      transcribe: vi.fn(),
      speech: vi.fn(),
    },
  });
  cancelVoice();
  useApp.setState({
    data: {
      session: { id: "session" },
      credentials: { elevenlabs: true },
    } as State,
  });
  useMedia.setState({
    status: { state: "idle", muted: false, voice: "idle", duration: 0 },
  });
});
test("cancelling while microphone permission is pending stops the late stream without transcription", async () => {
  let grant: (stream: MediaStream) => void = () => {};
  const stop = vi.fn();
  vi.stubGlobal("navigator", {
    mediaDevices: {
      getUserMedia: () =>
        new Promise<MediaStream>((resolve) => {
          grant = resolve;
        }),
    },
  });
  const pending = voiceNote();
  cancelVoice();
  grant({ getTracks: () => [{ stop }] } as unknown as MediaStream);
  await pending;
  expect(stop).toHaveBeenCalledOnce();
  expect(window.desktop.transcribe).not.toHaveBeenCalled();
  expect(useMedia.getState().status.voice).toBe("idle");
});
test("muting while speech is in flight never starts audio playback", async () => {
  let finish: (bytes: Uint8Array) => void = () => {};
  vi.mocked(window.desktop.speech).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const AudioConstructor = vi.fn();
  vi.stubGlobal("Audio", AudioConstructor);
  const pending = speak("An evidence-backed question");
  cancelVoice();
  finish(new Uint8Array([1, 2, 3]));
  await pending;
  expect(AudioConstructor).not.toHaveBeenCalled();
});
