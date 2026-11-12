#!/usr/bin/env node
// One-command dev launcher: `npm run dev` (repo root or frontend/) bootstraps and starts
// the FastAPI backend and the Vite frontend together. Dependency-free and cross-platform.
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const BACKEND = join(ROOT, "backend");
const FRONTEND = join(ROOT, "frontend");
const VENV = join(BACKEND, ".venv");
const IS_WIN = process.platform === "win32";
const BACKEND_PORT = process.env.BACKEND_PORT || "8000";
const FRONTEND_PORT = process.env.FRONTEND_PORT || "5173";

const c = (code) => (s) => (process.stdout.isTTY ? `\x1b[${code}m${s}\x1b[0m` : s);
const red = c("31"), cyan = c("36"), magenta = c("35"), dim = c("2"), bold = c("1");
const log = (msg) => console.log(`${bold(cyan("[nexus]"))} ${msg}`);
const fail = (msg) => {
  console.error(`${bold(red("[nexus]"))} ${msg}`);
  process.exit(1);
};

// npm/npx are .cmd shims on Windows and need a shell; pass one command string (args are constants).
const viaShell = (cmd, args) =>
  IS_WIN && (cmd === "npm" || cmd === "npx") ? [`${cmd} ${args.join(" ")}`, [], { shell: true }] : [cmd, args, {}];

function run(cmd, args, opts = {}) {
  const [c0, a0, extra] = viaShell(cmd, args);
  const r = spawnSync(c0, a0, { stdio: "inherit", ...extra, ...opts });
  if (r.status !== 0) fail(`Command failed: ${cmd} ${args.join(" ")}`);
}

function findSystemPython() {
  const candidates = process.env.PYTHON ? [[process.env.PYTHON]] : IS_WIN ? [["py", "-3"], ["python"], ["python3"]] : [["python3"], ["python"]];
  for (const [cmd, ...pre] of candidates) {
    const r = spawnSync(cmd, [...pre, "-c", "import sys; assert sys.version_info >= (3, 10)"], { stdio: "ignore" });
    if (r.status === 0) return [cmd, pre];
  }
  fail("Python 3.10+ not found. Install it or set PYTHON=/path/to/python.");
}

function ensureBackend() {
  const py = IS_WIN ? join(VENV, "Scripts", "python.exe") : join(VENV, "bin", "python");
  if (!existsSync(py)) {
    log("Creating backend virtualenv (first run)...");
    const [cmd, pre] = findSystemPython();
    run(cmd, [...pre, "-m", "venv", VENV]);
  }
  // Reinstall Python deps only when requirements.txt changes.
  const reqFile = join(BACKEND, "requirements.txt");
  const stamp = join(VENV, ".requirements.sha256");
  const hash = createHash("sha256").update(readFileSync(reqFile)).digest("hex");
  if (!existsSync(stamp) || readFileSync(stamp, "utf8").trim() !== hash) {
    log("Installing backend dependencies...");
    run(py, ["-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", reqFile]);
    writeFileSync(stamp, hash);
  }
  return py;
}

function ensureFrontend() {
  if (!existsSync(join(FRONTEND, "node_modules", ".bin"))) {
    log("Installing frontend dependencies (first run)...");
    run("npm", ["install", "--no-audit", "--no-fund"], { cwd: FRONTEND });
  }
}

async function backendHealthy() {
  try {
    const r = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/health`, { signal: AbortSignal.timeout(1500) });
    return r.ok;
  } catch {
    return false;
  }
}

const children = [];
let shuttingDown = false;

function start(name, color, cmd, args, opts) {
  const [c0, a0, extra] = viaShell(cmd, args);
  const child = spawn(c0, a0, { stdio: ["ignore", "pipe", "pipe"], ...extra, ...opts });
  const prefix = color(`[${name}]`.padEnd(6));
  for (const stream of [child.stdout, child.stderr]) {
    let buf = "";
    stream.on("data", (d) => {
      buf += d.toString();
      const lines = buf.split(/\r?\n/);
      buf = lines.pop();
      for (const line of lines) console.log(`${prefix} ${line}`);
    });
  }
  child.on("exit", (code) => {
    if (!shuttingDown) {
      console.log(`${prefix} exited with code ${code}`);
      shutdown(code ?? 1);
    }
  });
  children.push(child);
}

function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  log("Shutting down...");
  for (const ch of children) {
    if (ch.exitCode !== null) continue;
    // On Windows the shell wrapper must be killed as a tree, otherwise uvicorn/vite are orphaned.
    if (IS_WIN) spawnSync("taskkill", ["/pid", String(ch.pid), "/T", "/F"], { stdio: "ignore" });
    else ch.kill("SIGTERM");
  }
  setTimeout(() => process.exit(code), 300);
}
process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

async function waitForHealth(timeoutMs = 90_000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs && !shuttingDown) {
    if (await backendHealthy()) return true;
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

log(bold("J&J GraphRAG Nexus - starting dev environment"));
const py = ensureBackend();
ensureFrontend();

if (await backendHealthy()) {
  log(`Backend already running on :${BACKEND_PORT} - reusing it.`);
} else {
  start("api", magenta, py, ["-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", BACKEND_PORT, "--reload", "--reload-dir", "app"], {
    cwd: BACKEND,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
  });
}

// Start Vite only once the API is healthy so the UI never hits proxy errors while the graph loads.
if (!(await waitForHealth())) {
  if (!shuttingDown) log(red(`Backend did not become healthy on :${BACKEND_PORT} within 90s - check the [api] logs above.`));
  shutdown(1);
} else {
  start("web", cyan, "npx", ["vite", "--port", FRONTEND_PORT, "--host", "0.0.0.0", "--strictPort"], {
    cwd: FRONTEND,
    env: { ...process.env, VITE_BACKEND_URL: process.env.VITE_BACKEND_URL || `http://127.0.0.1:${BACKEND_PORT}` },
  });
  log(`${bold("Ready")}  App: ${cyan(`http://localhost:${FRONTEND_PORT}`)}  ${dim("|")}  API docs: ${magenta(`http://localhost:${BACKEND_PORT}/docs`)}  ${dim("(Ctrl+C to stop)")}`);
}
