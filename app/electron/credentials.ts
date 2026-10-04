/** Provider secrets are encrypted with the OS key store, never saved in sessions. */
import { safeStorage } from "electron";
import { promises as fs } from "node:fs";
export class Credentials {
  constructor(private file: string) {}
  async read(): Promise<Record<string, string>> {
    try {
      const raw = await fs.readFile(this.file);
      if (!safeStorage.isEncryptionAvailable())
        throw new Error("OS secure storage is unavailable.");
      return JSON.parse(safeStorage.decryptString(raw));
    } catch (error: any) {
      if (error.code === "ENOENT") return {};
      throw error;
    }
  }
  async save(patch: Record<string, string>) {
    if (!safeStorage.isEncryptionAvailable())
      throw new Error(
        "OS secure storage is unavailable; credentials were not saved.",
      );
    const values = { ...(await this.read()), ...patch };
    const temporary = this.file + ".tmp";
    await fs.writeFile(
      temporary,
      safeStorage.encryptString(JSON.stringify(values)),
      { mode: 0o600 },
    );
    await fs.rename(temporary, this.file);
    return values;
  }
}
