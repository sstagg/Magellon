/**
 * Post-import result verification for the 24dec03a session.
 *
 * Depends on import-magellon-project.spec.ts having run first and written
 * tests/e2e/screenshots/import-magellon-project/job_id.txt.
 *
 * Checks three things:
 *   1. Job summary API — CTF tasks completed, MotionCor tasks failed (no GPU)
 *   2. UI — session and images visible in the panel
 *   3. Ops event log — DuckDB query returns expected category/status rows
 */
import { expect, test } from "@playwright/test";
import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const FRONTEND  = process.env.MAGELLON_E2E_FRONTEND  ?? "http://localhost:8080";
const BACKEND   = process.env.MAGELLON_E2E_BACKEND   ?? "http://127.0.0.1:8000";
const USERNAME  = process.env.MAGELLON_E2E_USERNAME  ?? "super";
const PASSWORD  = process.env.MAGELLON_E2E_PASSWORD  ?? "behd1d2";
const CORE_DIR  = path.resolve(process.cwd(), "..", "CoreService");

const SHOTS = path.join(process.cwd(), "tests", "e2e", "screenshots", "verify-import-results");
const JOB_ID_FILE = path.join(
  process.cwd(), "tests", "e2e", "screenshots", "import-magellon-project", "job_id.txt",
);

// Stage numbers → readable labels (matches CoreService _TASK_STAGE_LABEL)
const STAGE_LABEL: Record<number, string> = { 0: "import", 1: "motioncor", 2: "ctf" };

interface AuthBody { access_token: string; user_id: string; username: string }
interface SummaryBody {
  job_id: string;
  total_tasks: number;
  terminal_tasks: number;
  totals: Record<string, number>;
  by_category: Record<string, Record<string, number>>;
  derived_status: string;
}

async function login(): Promise<AuthBody> {
  const res = await fetch(`${BACKEND}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: USERNAME, password: PASSWORD }),
  });
  if (!res.ok) throw new Error(`login failed: ${res.status}`);
  return res.json() as Promise<AuthBody>;
}

async function fetchSummary(jobId: string, token: string): Promise<SummaryBody> {
  const res = await fetch(`${BACKEND}/export/job/${jobId}/summary`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`summary fetch failed: ${res.status}`);
  return res.json() as Promise<SummaryBody>;
}

/** Poll until all tasks reach a terminal state or timeout. */
async function waitForAllTerminal(
  jobId: string,
  token: string,
  timeoutMs = 20 * 60 * 1000,
  pollMs = 8_000,
): Promise<SummaryBody> {
  const deadline = Date.now() + timeoutMs;
  let last: SummaryBody | null = null;
  while (Date.now() < deadline) {
    last = await fetchSummary(jobId, token);
    console.log(
      `  [poll] total=${last.total_tasks} terminal=${last.terminal_tasks}` +
      ` ctf_done=${last.by_category?.ctf?.completed ?? 0}` +
      ` mc_failed=${last.by_category?.motioncor?.failed ?? 0}`,
    );
    if (last.total_tasks > 0 && last.terminal_tasks >= last.total_tasks) break;
    await new Promise(r => setTimeout(r, pollMs));
  }
  if (!last) throw new Error("No summary received");
  return last;
}

// ────────────────────────────────────────────────────────────
test.describe("verify 24dec03a import results", () => {
  test.setTimeout(25 * 60 * 1000);

  let token = "";
  let jobId = "";

  test.beforeAll(async () => {
    fs.mkdirSync(SHOTS, { recursive: true });

    if (!fs.existsSync(JOB_ID_FILE)) {
      throw new Error(
        `job_id.txt not found at ${JOB_ID_FILE}. ` +
        "Run import-magellon-project.spec.ts first.",
      );
    }
    jobId = fs.readFileSync(JOB_ID_FILE, "utf-8").trim();
    const auth = await login();
    token = auth.access_token;
    console.log(`Verifying job ${jobId}`);
  });

  // ── 1. API: task counts ──────────────────────────────────
  test("job summary shows CTF completed and MotionCor terminal", async () => {
    const summary = await waitForAllTerminal(jobId, token);

    fs.writeFileSync(
      path.join(SHOTS, "job-summary.json"),
      JSON.stringify(summary, null, 2),
    );
    console.log("Final summary:", JSON.stringify(summary.by_category, null, 2));

    // All tasks should be terminal
    expect(summary.terminal_tasks).toEqual(summary.total_tasks);

    // CTF stage: actual micrographs (pixel_size <= 5) should be completed
    const ctfCompleted = summary.by_category?.ctf?.completed ?? 0;
    expect(ctfCompleted).toBeGreaterThanOrEqual(200);

    // Import stage: atlas/non-CTF images should also be completed (swept by importer)
    const importDone = summary.by_category?.import?.completed ?? 0;
    expect(importDone).toBeGreaterThanOrEqual(1);

    // Overall derived status should be completed
    expect(summary.derived_status).toBe("completed");
  });

  // ── 2. Filesystem: CTF output dirs ──────────────────────
  test("CTF result directories exist on disk", async () => {
    const ctfDir = path.join("C:", "magellon", "gpfs", "home", "24dec03a", "ctf");
    expect(fs.existsSync(ctfDir), `ctf dir should exist: ${ctfDir}`).toBe(true);
    const entries = fs.readdirSync(ctfDir);
    expect(entries.length).toBeGreaterThan(100);
    console.log(`CTF dir has ${entries.length} entries`);
    fs.writeFileSync(
      path.join(SHOTS, "ctf-dir-listing.txt"),
      entries.slice(0, 20).join("\n") + `\n...(${entries.length} total)`,
    );
  });

  // ── 3. DuckDB: ops event log ─────────────────────────────
  test("ops event log contains expected categories", () => {
    const result = execSync(
      `python scripts/query_ops.py summary`,
      { cwd: CORE_DIR, encoding: "utf-8" },
    );
    console.log("Ops log summary:\n", result);
    fs.writeFileSync(path.join(SHOTS, "ops-summary.txt"), result);

    expect(result).toContain("ctf");
    expect(result).toContain("completed");
  });

  // ── 4. API: session visible in /web/sessions ────────────
  test("session 24DEC03A is returned by the sessions API", async () => {
    const res = await fetch(`${BACKEND}/web/sessions`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.ok, `sessions API returned ${res.status}`).toBe(true);
    const sessions = await res.json() as Array<{ name: string; oid: string }>;
    const names = sessions.map(s => s.name?.toUpperCase());
    console.log("Sessions from API:", names.slice(0, 5));
    expect(names).toContain("24DEC03A");
  });
});
