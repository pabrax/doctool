import { defineConfig } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { rmSync } from "node:fs";
import path from "node:path";

const PORT = 8124;
const e2e = path.join(import.meta.dirname, "e2e");
const win = process.platform === "win32";
const python = path.join(import.meta.dirname, "..", ".venv", win ? "Scripts/python.exe" : "bin/python");

// Runs in the main Playwright process only (workers re-load this file and must not wipe the data
// dir under a running server). The web server starts after this block, so the data dir is free.
if (process.env.TEST_WORKER_INDEX === undefined) {
  rmSync(path.join(e2e, ".data"), { recursive: true, force: true });
  rmSync(path.join(e2e, ".fixtures"), { recursive: true, force: true });
  execFileSync(python, ["-I", path.join(e2e, "make_pdfs.py"), path.join(e2e, ".fixtures")], {
    stdio: "inherit",
  });
}

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 }, // Ghostscript/pikepdf tasks can exceed 5 s on a busy laptop
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    // Local default: the Edge already installed. CI sets E2E_CHANNEL=chromium (bundled browser).
    channel: (process.env.E2E_CHANNEL ?? "msedge") === "chromium" ? undefined : (process.env.E2E_CHANNEL ?? "msedge"),
    locale: "en-US",
    trace: "retain-on-failure",
    acceptDownloads: true,
  },
  webServer: {
    command: `"${python}" -m doctool`,
    cwd: "../api",
    url: `http://127.0.0.1:${PORT}/api/v1/health`,
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      DOCTOOL_PORT: String(PORT),
      DOCTOOL_DATA_DIR: "../web/e2e/.data",
      DOCTOOL_WEB_DIR: "../web/dist",
    },
  },
});
