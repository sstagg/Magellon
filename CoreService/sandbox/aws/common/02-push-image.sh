#!/usr/bin/env bash
# Build and push the motioncor GPU image to ECR. Idempotent: creates repo if missing.
# The MotionCor2 binary is copied from the plugin dir so we don't duplicate ~3MB.

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${SCRIPT_DIR}/activate.sh"

ROOT="${SCRIPT_DIR}/.."
IMAGE_DIR="${ROOT}/image"
PLUGIN_DIR="${ROOT}/../../../plugins/magellon_motioncor_plugin"
BINARY="${PLUGIN_DIR}/motioncor2_binaryfiles/MotionCor2_1.6.4_Cuda121_Mar312023"

if [ ! -f "$BINARY" ]; then
  echo "ERROR: binary not found at $BINARY" >&2
  exit 1
fi

# Stage the binary next to the Dockerfile so the COPY succeeds
cp "$BINARY" "${IMAGE_DIR}/MotionCor2"

# Create ECR repo
if ! aws ecr describe-repositories --repository-names "$ECR_REPO" >/dev/null 2>&1; then
  echo "Creating ECR repo ${ECR_REPO}..."
  aws ecr create-repository \
    --repository-name "$ECR_REPO" \
    --image-scanning-configuration scanOnPush=true \
    --tags ${TAGS_CLI} >/dev/null
fi

# Log in to ECR
aws ecr get-login-password --region "$AWS_DEFAULT_REGION" \
  | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_DEFAULT_REGION}.amazonaws.com"

# Build (linux/amd64 — g4dn is x86_64; matters if building on ARM Mac)
TAG=$(date +%Y%m%d-%H%M%S)
docker build --platform=linux/amd64 \
  -t "${ECR_URI}:${TAG}" \
  -t "${ECR_URI}:latest" \
  "$IMAGE_DIR"

docker push "${ECR_URI}:${TAG}"
docker push "${ECR_URI}:latest"

# Clean up staged binary
rm -f "${IMAGE_DIR}/MotionCor2"

echo
echo "Pushed:"
echo "  ${ECR_URI}:${TAG}"
echo "  ${ECR_URI}:latest"
