import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const FRONTEND = process.env.MAGELLON_E2E_FRONTEND ?? "http://localhost:8080";
const BACKEND  = process.env.MAGELLON_E2E_BACKEND  ?? "http://127.0.0.1:8000";
const USERNAME = process.env.MAGELLON_E2E_USERNAME  ?? "super";
const PASSWORD = process.env.MAGELLON_E2E_PASSWORD  ?? "behd1d2";
const SHOTS    = path.join(process.cwd(), "tests", "e2e", "screenshots", "import-magellon-project");
const RESET_SCRIPT = path.resolve(process.cwd(), "..", "CoreService", "scripts", "reset_demo_data.py");

interface AuthBody {
  access_token: string;
  user_id: string;
  username: string;
}

const login = async (): Promise<AuthBody> => {
  const res = await fetch(`${BACKEND}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: USERNAME, password: PASSWORD }),
  });
  if (!res.ok) throw new Error(`login failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as AuthBody;
};

test("imports the 24dec03a Magellon project with live progress feedback", async ({ page, context }) => {
  test.setTimeout(35 * 60 * 1000);
  fs.mkdirSync(SHOTS, { recursive: true });

  if (process.env.MAGELLON_E2E_RESET_DEMO === "1") {
    execFileSync("python", [RESET_SCRIPT, "--yes", "--clear-session-dir", "24dec03a"], { stdio: "inherit" });
  }

  // ── Auth ──────────────────────────────────────────────────────────────────
  const auth = await login();
  await context.addInitScript(
    ({ token, userId, username }) => {
      localStorage.setItem("access_token", token);
      localStorage.setItem(
        "currentUser",
        JSON.stringify({ id: userId, username, active: true, change_password_required: false }),
      );
      localStorage.setItem("currentUserId", userId);
    },
    { token: auth.access_token, userId: auth.user_id, username: auth.username },
  );

  // ── Navigate to import page ───────────────────────────────────────────────
  await page.goto(`${FRONTEND}/en/panel/import-job`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Magellon Data Importer" })).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: path.join(SHOTS, "01-import-page.png"), fullPage: true });

  // ── Dismiss any dialog left open from a previous run ─────────────────────
  // The component auto-resumes a running/completed import on mount; if a
  // background job from a prior run is still in the DB this dialog blocks the
  // file browser.  Wait for it to reach a terminal state (close button enabled)
  // then dismiss it before proceeding.
  {
    const staleDialog = page.getByRole("dialog", { name: /Magellon import|Importing/i });
    if (await staleDialog.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await page.screenshot({ path: path.join(SHOTS, "01b-stale-dialog.png") });
      const closeBtn = staleDialog.getByRole("button", { name: "Close" });
      // 30 s: completed/failed jobs show close immediately; if still running
      // after 30 s there's a live import in progress — fail fast.
      await expect(closeBtn).toBeEnabled({ timeout: 30_000 });
      await closeBtn.click();
      await expect(staleDialog).not.toBeVisible({ timeout: 10_000 });
    }
  }

  // ── Magellon tab + file browser ───────────────────────────────────────────
  await page.getByRole("tab", { name: "Magellon" }).click();
  await expect(page.getByText("Current path: /gpfs")).toBeVisible({ timeout: 30_000 });

  await page.getByTestId("import-file-24dec03a").dblclick();
  await expect(page.getByText("Current path: /gpfs/24dec03a")).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: path.join(SHOTS, "02-project-folder.png"), fullPage: true });

  await page.getByTestId("import-file-session.json").click();
  await expect(page.getByText(/Selected file: .*session\.json/)).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: path.join(SHOTS, "03-session-selected.png"), fullPage: true });

  // ── Start import ──────────────────────────────────────────────────────────
  await page.getByTestId("magellon-import-start").click();

  // Dialog opens — title is "Magellon import" before summary loads, then
  // "Importing <session>" after first poll. Match either form.
  const dialog = page.getByRole("dialog", { name: /Magellon import|Importing/i });
  await expect(dialog).toBeVisible({ timeout: 15_000 });
  await page.screenshot({ path: path.join(SHOTS, "04-dialog-opened.png") });

  // Job ID must appear (proves the backend accepted the job)
  await expect(dialog.getByText(/Job:/)).toBeVisible({ timeout: 60_000 });
  await page.screenshot({ path: path.join(SHOTS, "05-job-id-visible.png") });

  // Pipeline steps table appears once the first step_progress socket event arrives
  await expect(dialog.getByText("PNG Conversion")).toBeVisible({ timeout: 120_000 });
  await expect(dialog.getByText("FFT Computation")).toBeVisible({ timeout: 10_000 });
  await expect(dialog.getByText("CTF Estimation")).toBeVisible({ timeout: 10_000 });
  await expect(dialog.getByText("Motion Correction")).toBeVisible({ timeout: 10_000 });
  await page.screenshot({ path: path.join(SHOTS, "06-pipeline-steps.png") });

  // Wait for overall progress to reach 100% on the 307-image session.
  // (Display is "<pct>% · 307 images" after the dialog refactor; pre-refactor
  // was "X / 307 images".)
  await expect(dialog.getByText(/100%\s*·\s*307\s*images/)).toBeVisible({
    timeout: 30 * 60 * 1000,
  });
  await page.screenshot({ path: path.join(SHOTS, "07-complete.png"), fullPage: true });

  // Status chip must say "completed" — scope to the MUI chip label to avoid
  // matching "Import completed successfully." in the Alert above it.
  await expect(
    dialog.locator(".MuiChip-label").filter({ hasText: /^completed$/ }),
  ).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: path.join(SHOTS, "08-completed-status.png"), fullPage: true });

  // ── Capture final dialog text ─────────────────────────────────────────────
  const dialogText = await dialog.innerText();
  fs.writeFileSync(path.join(SHOTS, "progress-modal.txt"), dialogText);
  expect(dialogText).toContain("Job:");
  expect(dialogText).toContain("PNG Conversion");
  expect(dialogText).toContain("CTF Estimation");

  // Persist job_id so verify-import-results.spec.ts can consume it
  const jobIdMatch = dialogText.match(
    /Job:\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i,
  );
  if (jobIdMatch) {
    fs.writeFileSync(path.join(SHOTS, "job_id.txt"), jobIdMatch[1]);
    console.log("Job ID:", jobIdMatch[1]);
  }
});
