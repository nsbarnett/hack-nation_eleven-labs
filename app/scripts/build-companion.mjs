/** Release only local runtime assets. Synthetic fixtures never enter this bundle. */
import { build } from "esbuild";
import { cp, mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { resolve, join } from "node:path";
import { zipSync } from "fflate";
const output = resolve("../release/extension/unpacked");
await mkdir(output, { recursive: true });
for (const entry of ["background", "content", "surface", "options"])
  await build({
    entryPoints: [`extension/${entry}.ts`],
    outfile: join(output, `${entry}.js`),
    bundle: true,
    format: "iife",
    target: "chrome120",
    minify: true,
  });
for (const name of [
  "manifest.json",
  "surface.html",
  "surface.css",
  "options.html",
  "options.css",
])
  await cp(`extension/${name}`, join(output, name));
await cp("../docs/EXTENSION.md", join(output, "README.md"));
const files = {};
for (const name of await readdir(output))
  files[name] = new Uint8Array(await readFile(join(output, name)));
const archive = zipSync(files, { level: 6 });
await mkdir("dist/downloads", { recursive: true });
await writeFile("../release/extension/apprentice-extension.zip", archive);
await writeFile("dist/downloads/apprentice-extension.zip", archive);
await mkdir("dist/ocr", { recursive: true });
await cp(
  "node_modules/tesseract.js/dist/worker.min.js",
  "dist/ocr/worker.min.js",
);
for (const name of await readdir("node_modules/tesseract.js-core"))
  if (/\.wasm(\.js)?$/.test(name))
    await cp(`node_modules/tesseract.js-core/${name}`, `dist/ocr/${name}`);
await cp(
  "node_modules/@tesseract.js-data/eng/4.0.0/eng.traineddata.gz",
  "dist/ocr/eng.traineddata.gz",
);
for (const [name, path] of Object.entries({
  "TESSERACT-LICENSE": "node_modules/tesseract.js/LICENSE.md",
  "MEDIABUNNY-LICENSE": "node_modules/mediabunny/LICENSE",
}))
  await cp(path, `dist/ocr/${name}`).catch(() => {});
console.log("Built companion ZIP, unpacked extension, and local OCR assets.");
