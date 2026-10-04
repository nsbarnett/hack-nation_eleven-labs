/** All decoding, OCR and encoding happens locally, one frame/job at a time. */
import {
  ALL_FORMATS,
  BlobSource,
  CanvasSink,
  Conversion,
  Input,
  Output,
  StreamTarget,
  VideoSampleSink,
  WebMOutputFormat,
} from "mediabunny";
import { createWorker, type Worker as OCRWorker } from "tesseract.js";
import { detectLines } from "./detect";
import { paintCovers, validateCovers } from "./geometry";
import { appendAsset, beginAsset, finishAsset } from "../web/localMedia";
import type { Cover, Segment } from "./types";

let ocr: OCRWorker | undefined;
const post = (data: unknown) => self.postMessage(data);
async function detect(blob: Blob, width: number, height: number) {
  ocr ??= await createWorker("eng", 1, {
    workerPath: "/ocr/worker.min.js",
    corePath: "/ocr/",
    langPath: "/ocr/",
    workerBlobURL: false,
  });
  const result = await ocr.recognize(blob, {}, { blocks: true, text: false });
  const lines =
    result.data.blocks?.flatMap((b) => b.paragraphs.flatMap((p) => p.lines)) ||
    [];
  return detectLines(lines, width, height); // Never persist or post OCR text.
}
self.onmessage = async ({ data }) => {
  let input: Input | undefined;
  try {
    if (data.op === "detect") {
      const bitmap = await createImageBitmap(data.blob);
      const { width, height } = bitmap;
      bitmap.close();
      post({
        type: "detected",
        findings: await detect(data.blob, width, height),
      });
    } else {
      input = new Input({
        source: new BlobSource(data.blob),
        formats: ALL_FORMATS,
      });
      const track = await input.getPrimaryVideoTrack();
      if (!track || !(await track.canDecode()))
        throw new Error(
          "This browser cannot decode this recording. Use a current Chrome or Edge browser.",
        );
      const duration = await input.computeDuration();
      if (!Number.isFinite(duration) || duration <= 0 || duration > 610)
        throw new Error(
          "The recording duration could not be read or exceeds the local processing limit.",
        );
      const segment: Segment = {
        ...data.segment,
        duration,
        width: track.displayWidth,
        height: track.displayHeight,
      };
      post({ type: "metadata", segment });
      if (data.op === "scan") {
        const sink = new VideoSampleSink(track),
          thumb = new OffscreenCanvas(32, 18),
          tc = thumb.getContext("2d", { willReadFrequently: true })!;
        const canvas = new OffscreenCanvas(
          Math.min(1600, segment.width),
          Math.round(segment.height * Math.min(1, 1600 / segment.width)),
        );
        const context = canvas.getContext("2d")!;
        let previous: Uint8ClampedArray | undefined,
          lastOcr = -1,
          count = 0,
          lastTime = 0,
          dimensions = "";
        for await (const sample of sink.samples()) {
          try {
            sample.draw(tc, 0, 0, 32, 18);
            const pixels = tc.getImageData(0, 0, 32, 18).data;
            let difference = 0;
            if (previous)
              for (let i = 0; i < pixels.length; i += 4)
                difference +=
                  Math.abs(pixels[i] - previous[i]) +
                  Math.abs(pixels[i + 1] - previous[i + 1]) +
                  Math.abs(pixels[i + 2] - previous[i + 2]);
            const size = `${sample.displayWidth}x${sample.displayHeight}`;
            const cut =
              !!previous &&
              (difference / (32 * 18 * 3) > 42 || size !== dimensions);
            previous = pixels;
            dimensions = size;
            if (cut) post({ type: "cut", time: sample.timestamp });
            if (sample.timestamp - lastTime > 0.75)
              post({
                type: "gap",
                message: `No decoded frames between ${lastTime.toFixed(1)}s and ${sample.timestamp.toFixed(1)}s.`,
              });
            lastTime = sample.timestamp;
            if (sample.timestamp - lastOcr >= 0.5 || cut) {
              if (++count > 1500)
                throw new Error(
                  "Local scan limit reached. Review the remaining recording manually.",
                );
              sample.draw(context, 0, 0, canvas.width, canvas.height);
              const blob = await canvas.convertToBlob({ type: "image/png" });
              post({
                type: "findings",
                time: sample.timestamp,
                findings: await detect(blob, canvas.width, canvas.height),
                progress: Math.min(1, sample.timestamp / duration),
                count,
              });
              lastOcr = sample.timestamp;
            }
          } finally {
            sample.close();
          }
        }
        post({ type: "done" });
      } else if (data.op === "render") {
        const covers: Cover[] = data.covers;
        validateCovers(covers, [segment], { [segment.name]: data.cuts || [] });
        const name = data.name as string;
        await beginAsset(data.guest, data.session, name, "video/webm", {
          purpose: "redacted",
          revision: data.revision,
          ...segment,
          name,
        });
        let offset = 0;
        const output = new Output({
          format: new WebMOutputFormat({ appendOnly: true }),
          target: new StreamTarget(
            new WritableStream({
              async write(chunk) {
                if (chunk.position !== offset)
                  throw new Error(
                    "Encoder attempted a non-sequential write. Original media is retained.",
                  );
                await appendAsset(data.guest, data.session, name, chunk.data);
                offset += chunk.data.byteLength;
              },
            }),
            { chunked: true, chunkSize: 1024 * 1024 },
          ),
        });
        const canvas = new OffscreenCanvas(segment.width, segment.height),
          context = canvas.getContext("2d")!;
        const conversion = await Conversion.init({
          input,
          output,
          video: {
            codec: "vp8",
            bitrate: 2_000_000,
            forceTranscode: true,
            process(sample) {
              sample.draw(context, 0, 0, canvas.width, canvas.height);
              paintCovers(
                context,
                covers,
                segment.name,
                sample.timestamp,
                canvas.width,
                canvas.height,
                sample.timestamp + sample.duration,
              );
              return canvas;
            },
          },
        });
        if (!conversion.isValid || conversion.discardedTracks.length)
          throw new Error(
            "This browser cannot encode all recording tracks. No unredacted fallback will be exported.",
          );
        conversion.onProgress = (progress) =>
          post({ type: "progress", progress });
        await conversion.execute();
        await finishAsset(data.guest, data.session, name);
        post({ type: "done", name });
      } else if (data.op === "frame") {
        const frame = await new CanvasSink(track, {
          width: Math.min(1280, segment.width),
          poolSize: 1,
        }).getCanvas(Math.max(data.time, await track.getFirstTimestamp()));
        if (!frame)
          throw new Error("No video frame is available at this time.");
        const canvas = frame.canvas as OffscreenCanvas;
        post({
          type: "done",
          blob: await canvas.convertToBlob({
            type: "image/jpeg",
            quality: 0.8,
          }),
        });
      }
    }
  } catch (error) {
    post({
      type: "error",
      message:
        error instanceof Error ? error.message : "Local processing failed.",
    });
  } finally {
    input?.dispose();
  }
};
