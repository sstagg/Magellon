import { expect, test } from "@playwright/test";

const BACKEND = process.env.MAGELLON_E2E_BACKEND ?? "http://127.0.0.1:8000";
const USERNAME = process.env.MAGELLON_E2E_USERNAME ?? "super";
const PASSWORD = process.env.MAGELLON_E2E_PASSWORD ?? "behd1d2";

interface AuthBody {
  access_token: string;
}

async function login(): Promise<AuthBody> {
  const res = await fetch(`${BACKEND}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: USERNAME, password: PASSWORD }),
  });
  if (!res.ok) throw new Error(`login failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as AuthBody;
}

const defaultData = {
  pixel_size: 0.739,
  acceleration_voltage: 300,
  spherical_aberration: 2.7,
  magnification: 5000,
  dose: 1,
  defocus: 15000,
  amplitude_contrast: 0.07,
  detector_pixel_size: 5,
  flip_gain: 0,
  rot_gain: 0,
};

test.describe("optional importer source e2e", () => {
  test("EPU import endpoint accepts configured fixture", async () => {
    test.skip(!process.env.MAGELLON_E2E_EPU_DIR, "set MAGELLON_E2E_EPU_DIR to run");
    test.setTimeout(20 * 60 * 1000);

    const auth = await login();
    const res = await fetch(`${BACKEND}/export/epu-import`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${auth.access_token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        magellon_project_name: "e2e-epu",
        magellon_session_name: process.env.MAGELLON_E2E_EPU_SESSION ?? "e2e_epu",
        session_name: process.env.MAGELLON_E2E_EPU_SESSION ?? "e2e_epu",
        epu_dir_path: process.env.MAGELLON_E2E_EPU_DIR,
        if_do_subtasks: false,
        copy_images: false,
        default_data: defaultData,
      }),
    });

    expect(res.ok, await res.text()).toBe(true);
    const body = await res.json();
    expect(body.job_id).toBeTruthy();
  });

  test("SerialEM import endpoint accepts configured fixture", async () => {
    test.skip(!process.env.MAGELLON_E2E_SERIALEM_DIR, "set MAGELLON_E2E_SERIALEM_DIR to run");
    test.setTimeout(20 * 60 * 1000);

    const auth = await login();
    const res = await fetch(`${BACKEND}/export/serialem-import`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${auth.access_token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        magellon_project_name: "e2e-serialem",
        magellon_session_name: process.env.MAGELLON_E2E_SERIALEM_SESSION ?? "e2e_serialem",
        session_name: process.env.MAGELLON_E2E_SERIALEM_SESSION ?? "e2e_serialem",
        serial_em_dir_path: process.env.MAGELLON_E2E_SERIALEM_DIR,
        if_do_subtasks: false,
        copy_images: false,
        default_data: defaultData,
      }),
    });

    expect(res.ok, await res.text()).toBe(true);
    const body = await res.json();
    expect(body.job_id || body.message).toBeTruthy();
  });
});
