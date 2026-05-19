import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const FRONTEND = process.env.MAGELLON_E2E_FRONTEND ?? "http://localhost:8080";
const BACKEND = process.env.MAGELLON_E2E_BACKEND ?? "http://127.0.0.1:8000";
const USERNAME = process.env.MAGELLON_E2E_USERNAME ?? "super";
const PASSWORD = process.env.MAGELLON_E2E_PASSWORD ?? "behd1d2";
const SHOTS = path.join(process.cwd(), "tests", "e2e", "screenshots", "import-magellon-project");
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
  test.setTimeout(15 * 60 * 1000);
  fs.mkdirSync(SHOTS, { recursive: true });
  if (process.env.MAGELLON_E2E_RESET_DEMO === "1") {
    execFileSync("python", [RESET_SCRIPT, "--yes", "--clear-session-dir", "24dec03a"], { stdio: "inherit" });
  }

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

  await page.goto(`${FRONTEND}/en/panel/import-job`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Magellon Data Importer" })).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: path.join(SHOTS, "01-import-page.png"), fullPage: true });

  await page.getByRole("tab", { name: "Magellon" }).click();
  await expect(page.getByText("Current path: /gpfs")).toBeVisible({ timeout: 30_000 });

  await page.getByTestId("import-file-24dec03a").dblclick();
  await expect(page.getByText("Current path: /gpfs/24dec03a")).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: path.join(SHOTS, "02-project-folder.png"), fullPage: true });

  await page.getByTestId("import-file-session.json").click();
  await expect(page.getByText(/Selected file: .*session\.json/)).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: path.join(SHOTS, "03-session-selected.png"), fullPage: true });

  await page.getByTestId("magellon-import-start").click();
  const dialog = page.getByRole("dialog", { name: "Magellon import" });
  await expect(dialog).toBeVisible({ timeout: 15_000 });
  await expect(dialog.getByText(/Job:/)).toBeVisible({ timeout: 60_000 });
  await expect(dialog.getByText(/terminal/)).toBeVisible({ timeout: 120_000 });
  await expect(dialog.getByText(/Category/)).toBeVisible({ timeout: 120_000 });
  await expect(dialog.getByText(/\/307 terminal/)).toBeVisible({ timeout: 120_000 });
  await page.screenshot({ path: path.join(SHOTS, "04-progress-modal.png"), fullPage: true });

  const dialogText = await dialog.innerText();
  fs.writeFileSync(path.join(SHOTS, "progress-modal.txt"), dialogText);
  expect(dialogText).toContain("Job:");
});
