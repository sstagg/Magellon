#!/bin/bash

set -e

usage() {
  echo "Usage: $0 <UPLOADS_DIR> <EVALUATOR_DIR>"
  echo "  UPLOADS_DIR   → Absolute path to uploads directory"
  echo "  EVALUATOR_DIR → Absolute path to 2dclass_evaluator directory"
  exit 1
}

UPLOADS_DIR="$1"
EVALUATOR_DIR="$2"

if [ -z "$UPLOADS_DIR" ] || [ -z "$EVALUATOR_DIR" ]; then
  usage
fi

if [ ! -d "$UPLOADS_DIR" ]; then
  mkdir -p "$UPLOADS_DIR"
fi

if [ ! -d "$EVALUATOR_DIR" ]; then
  echo "❌ EVALUATOR_DIR does not exist: $EVALUATOR_DIR"
  exit 1
fi

# Defaults only
BACKEND_URL="http://localhost:8000"
FRONTEND_URL="http://localhost:3000"
FRONTEND_PORT=3000

cat > .env <<EOF
UPLOADS_DIR=$UPLOADS_DIR
EVALUATOR_DIR=$EVALUATOR_DIR
BACKEND_URL=$BACKEND_URL
FRONTEND_URL=$FRONTEND_URL
FRONTEND_PORT=$FRONTEND_PORT
EOF

echo "✅ .env created with default URLs:"
echo "  BACKEND_URL: $BACKEND_URL"
echo "  FRONTEND_URL: $FRONTEND_URL"
echo "  FRONTEND_PORT: $FRONTEND_PORT"

docker-compose up --build
