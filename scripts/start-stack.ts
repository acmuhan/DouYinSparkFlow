import { existsSync } from "node:fs";
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import process from "node:process";
import { config } from "dotenv";

config({ path: ".env.local" });

const isWindows = process.platform === "win32";
const npmCommand = isWindows ? "npm.cmd" : "npm";
const pythonCandidates = isWindows
  ? [".venv/Scripts/python.exe", "python"]
  : [".venv/bin/python", "python3", "python"];
const pythonCommand = pythonCandidates.find((candidate) => candidate === "python" || candidate === "python3" || existsSync(candidate)) ?? "python";
const forceProduction = process.argv.includes("--production");
const development = !forceProduction && (process.argv.includes("--dev") || process.env.NODE_ENV !== "production");
const apiHost = process.env.API_HOST ?? "0.0.0.0";
const apiPort = process.env.API_PORT ?? "8000";
const webHost = process.env.WEB_HOST ?? "0.0.0.0";
const webPort = process.env.WEB_PORT ?? "3000";

function runMigration() {
  const result = spawnSync(npmCommand, ["run", "db:migrate"], {
    stdio: "inherit",
    env: process.env,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`database migration exited with status ${result.status}`);
  }
}

function start(name: string, command: string, args: string[]) {
  const child = spawn(command, args, {
    stdio: "inherit",
    env: { ...process.env, SERVICE_NAME: name },
    shell: false,
  });
  child.once("error", (error) => {
    console.error(`[${name}] failed to start`, error);
    process.exitCode = 1;
  });
  child.once("exit", (code, signal) => {
    if (code !== 0 && signal !== "SIGTERM") {
      console.error(`[${name}] stopped (code=${code ?? "null"}, signal=${signal ?? "none"})`);
      process.exitCode = code ?? 1;
    }
  });
  return child;
}

function stopAll(children: ChildProcess[]) {
  for (const child of children) {
    if (!child.killed) child.kill("SIGTERM");
  }
}

function main() {
  console.log(`SparkFlow ${development ? "development" : "production"} stack`);
  runMigration();
  const children = [
    start("api", pythonCommand, [
      "-m", "uvicorn", "backend.app:app",
      "--host", apiHost, "--port", apiPort,
      ...(development ? ["--reload"] : []),
    ]),
    start("worker", pythonCommand, ["-m", "backend.worker"]),
    start("web", npmCommand, [
      "run", development ? "dev" : "start", "--",
      "--hostname", webHost, "--port", webPort,
    ]),
  ];
  const shutdown = () => stopAll(children);
  process.once("SIGINT", shutdown);
  process.once("SIGTERM", shutdown);
}

try {
  main();
} catch (error) {
  console.error("SparkFlow stack failed:", error);
  process.exitCode = 1;
}
