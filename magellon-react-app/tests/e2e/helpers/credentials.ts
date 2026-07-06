/**
 * Shared e2e credentials — the ONLY place a dev-stack default lives.
 *
 * Every spec imports from here; nothing else in tests/ may hardcode a
 * password (CI's repo-hygiene gate enforces this). Override against any
 * non-default stack:
 *
 *   MAGELLON_E2E_USERNAME=... MAGELLON_E2E_PASSWORD=... pnpm test:e2e
 */
export const E2E_USERNAME = process.env.MAGELLON_E2E_USERNAME ?? 'super';
export const E2E_PASSWORD = process.env.MAGELLON_E2E_PASSWORD ?? 'behd1d2';
