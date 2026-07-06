#!/bin/sh
# Generate the runtime config from env vars, then start nginx.
# One image serves any backend: set API_URL (and optionally WEB_API_URL)
# on the container — no rebuild, no source patching.
set -e

API_URL="${API_URL:-http://127.0.0.1:8000}"
WEB_API_URL="${WEB_API_URL:-${API_URL}/web}"

cat > /usr/share/nginx/html/config.js <<EOF
window.__MAGELLON_CONFIG__ = {
  SERVER_API_URL: "${API_URL}",
  SERVER_WEB_API_URL: "${WEB_API_URL}"
};
EOF

exec nginx -g "daemon off;"
