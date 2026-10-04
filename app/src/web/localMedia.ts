/** IndexedDB owns browser media. One chunk per row keeps recording memory bounded.
 * Every key includes guest + workflow; losing the guest cookie does not expose
 * a previous visitor's captures. No method in this module makes network requests.
 */
type Asset = { guest: string; session: string; name: string; type: string; size: number; chunks: number; partial: boolean };
const LIMIT = 100_000_000;
let database: Promise<IDBDatabase> | undefined;
function db() {
  return (database ??= new Promise((resolve, reject) => {
    const open = indexedDB.open("apprentice-media-v1", 1);
    open.onupgradeneeded = () => {
      const assets = open.result.createObjectStore("assets", { keyPath: ["guest", "session", "name"] });
      assets.createIndex("session", ["guest", "session"]);
      const chunks = open.result.createObjectStore("chunks", { keyPath: ["guest", "session", "name", "index"] });
      chunks.createIndex("asset", ["guest", "session", "name"]);
      chunks.createIndex("session", ["guest", "session"]);
    };
    open.onsuccess = () => resolve(open.result);
    open.onerror = () => reject(new Error("Browser storage is unavailable. Allow site storage before recording."));
  }));
}
function request<T>(value: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => { value.onsuccess = () => resolve(value.result); value.onerror = () => reject(value.error); });
}
function complete(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onabort = tx.onerror = () => reject(new Error("Browser storage is full or unavailable. Completed recording chunks were kept."));
  });
}
export async function listAssets(guest: string, session: string): Promise<Asset[]> {
  const tx = (await db()).transaction("assets", "readonly");
  return request(tx.objectStore("assets").index("session").getAll([guest, session]));
}
export async function beginAsset(guest: string, session: string, name: string, type: string) {
  const tx = (await db()).transaction("assets", "readwrite");
  const done = complete(tx);
  tx.objectStore("assets").put({ guest, session, name, type, size: 0, chunks: 0, partial: true } satisfies Asset);
  await done;
}
export async function appendAsset(guest: string, session: string, name: string, bytes: Uint8Array) {
  const connection = await db();
  const tx = connection.transaction(["assets", "chunks"], "readwrite");
  const done = complete(tx);
  const assets = tx.objectStore("assets");
  const rows = await request<Asset[]>(assets.index("session").getAll([guest, session]));
  const asset = rows.find((a) => a.name === name);
  if (!asset || rows.reduce((total, a) => total + a.size, 0) + bytes.length > LIMIT) {
    tx.abort();
    await done.catch(() => {});
    throw new Error("This workflow reached its 100 MB browser storage limit. Export or delete media before recording more.");
  }
  tx.objectStore("chunks").put({ guest, session, name, index: asset.chunks, blob: new Blob([new Uint8Array(bytes)], { type: asset.type }) });
  assets.put({ ...asset, chunks: asset.chunks + 1, size: asset.size + bytes.length });
  await done;
}
export async function finishAsset(guest: string, session: string, name: string) {
  const tx = (await db()).transaction("assets", "readwrite");
  const done = complete(tx);
  const store = tx.objectStore("assets");
  const asset = await request<Asset | undefined>(store.get([guest, session, name]));
  if (asset) store.put({ ...asset, partial: false });
  await done;
}
export async function readAsset(guest: string, session: string, name: string) {
  const tx = (await db()).transaction(["assets", "chunks"], "readonly");
  const [asset, chunks] = await Promise.all([
    request<Asset | undefined>(tx.objectStore("assets").get([guest, session, name])),
    request<{ index: number; blob: Blob }[]>(tx.objectStore("chunks").index("asset").getAll([guest, session, name])),
  ]);
  if (!asset || !chunks.length) throw new Error("This media is not stored in this browser. It may have been cleared or captured on another device.");
  return new Blob(chunks.sort((a, b) => a.index - b.index).map((part) => part.blob), { type: asset.type });
}
export async function removeAssets(guest: string, session: string, names?: Set<string>) {
  const tx = (await db()).transaction(["assets", "chunks"], "readwrite");
  const done = complete(tx);
  for (const storeName of ["assets", "chunks"]) {
    const cursor = tx.objectStore(storeName).index("session").openCursor([guest, session]);
    cursor.onsuccess = () => {
      const current = cursor.result;
      if (current) { if (!names || names.has(current.value.name)) current.delete(); current.continue(); }
    };
  }
  await done;
}
