/** Starts the bundled Python service and keeps its token outside renderer scope. */
import { app } from "electron";
import { spawn, ChildProcessWithoutNullStreams } from "node:child_process";
import { randomBytes } from "node:crypto";
import { createInterface } from "node:readline";
import path from "node:path";
import WebSocket from "ws";

export class Backend {
  private child?: ChildProcessWithoutNullStreams;
  private socket?: WebSocket;
  private token = randomBytes(32).toString("hex");
  private base = "";
  private closing = false;
  onEvent: (event: unknown) => void = () => {};
  constructor(readonly root: string) {}
  async start() {
    const repo = path.resolve(__dirname, "../..");
    const python =
      process.env.APPRENTICE_PYTHON ||
      path.join(
        repo,
        ".venv",
        process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
      );
    const executable = app.isPackaged
      ? path.join(
          process.resourcesPath,
          "backend",
          process.platform === "win32"
            ? "apprentice-backend.exe"
            : "apprentice-backend",
        )
      : python;
    this.child = spawn(executable, app.isPackaged ? [] : ["-m", "backend"], {
      cwd: app.isPackaged ? this.root : repo,
      windowsHide: true,
      stdio: "pipe",
    });
    this.child.stdin.end(
      JSON.stringify({ token: this.token, root: this.root }) + "\n",
    );
    this.child.stderr.on("data", () => {}); // Never forward provider internals or credentials to the renderer.
    const port = await new Promise<number>((resolve, reject) => {
      const timer = setTimeout(
        () => reject(new Error("Python service startup timed out.")),
        45000,
      );
      const lines = createInterface({ input: this.child!.stdout });
      lines.once("line", (line) => {
        clearTimeout(timer);
        try {
          resolve(JSON.parse(line).port);
        } catch {
          reject(new Error("Invalid backend startup response."));
        }
      });
      this.child!.once("error", () => {
        clearTimeout(timer);
        reject(
          new Error(
            "Python service could not start. See the development setup guide.",
          ),
        );
      });
      this.child!.once("exit", () => {
        clearTimeout(timer);
        reject(new Error("Python service exited during startup."));
      });
    });
    this.base = `http://127.0.0.1:${port}`;
    let ready = false;
    for (let attempt = 0; attempt < 100; attempt++) {
      try {
        await this.request("/state");
        ready = true;
        break;
      } catch {
        await new Promise((resolve) => setTimeout(resolve, 150));
      }
    }
    if (!ready) throw new Error("Python service did not become ready.");
    this.child.on("exit", () => {
      if (!this.closing)
        this.onEvent({
          type: "backend-offline",
          message:
            "The local service stopped. Recording has been stopped; restart the app to recover saved work.",
        });
    });
    this.connect();
  }
  private connect() {
    if (this.closing) return;
    this.socket = new WebSocket(this.base.replace("http:", "ws:") + "/events", {
      headers: { Authorization: `Bearer ${this.token}` },
    });
    this.socket.on("message", (raw) => {
      try {
        this.onEvent(JSON.parse(String(raw)));
      } catch {
        /* Ignore malformed service events. */
      }
    });
    this.socket.on("error", () => {});
    this.socket.on("close", () => {
      if (!this.closing) setTimeout(() => this.connect(), 1000);
    });
  }
  async request(
    route: string,
    body?: unknown,
    binary?: Uint8Array,
  ): Promise<any> {
    const response = await fetch(this.base + route, {
      method: body !== undefined || binary ? "POST" : "GET",
      headers: {
        Authorization: `Bearer ${this.token}`,
        "Content-Type": binary
          ? "application/octet-stream"
          : "application/json",
      },
      body: binary
        ? Buffer.from(binary)
        : body !== undefined
          ? JSON.stringify(body)
          : undefined,
      signal: AbortSignal.timeout(
        route === "/speech" || route === "/transcribe" ? 75000 : 45000,
      ),
    });
    if (!response.ok) {
      const result = (await response.json().catch(() => ({}))) as {
        detail?: string;
      };
      throw new Error(
        typeof result.detail === "string"
          ? result.detail
          : "The local service could not complete this request.",
      );
    }
    if (route === "/speech")
      return new Uint8Array(await response.arrayBuffer());
    return response.json();
  }
  stop() {
    this.closing = true;
    this.socket?.close();
    this.child?.kill();
  }
}
