#!/bin/sh
# Generate the runtime config from env vars, then start nginx.
# One image serves any backend: set API_URL (and optionally WEB_API_URL)
# on the container — no rebuild, no source patching.
set -e

# Empty API_URL means relative paths — nginx inside this container proxies
# /auth, /web, /image, etc. to the backend container. No CORS, no hardcoded host.
# Only set API_URL to an absolute URL when the backend is on a different host.
API_URL="${API_URL:-}"
WEB_API_URL="${WEB_API_URL:-${API_URL}/web}"

cat > /usr/share/nginx/html/config.js <<EOF
window.__MAGELLON_CONFIG__ = {
  SERVER_API_URL: "${API_URL}",
  SERVER_WEB_API_URL: "${WEB_API_URL}"
};
EOF

exec nginx -g "daemon off;"
