/* global window */
// Runtime configuration overrides. Loaded synchronously before the app
// bundle (see index.html). Empty in dev — configs.json defaults apply.
// The Docker image's entrypoint overwrites this file from env vars at
// container start (see docker-entrypoint.sh).
window.__MAGELLON_CONFIG__ = {};
