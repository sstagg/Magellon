#!/usr/bin/env bash
# Build SM-compatible image (FROM base motioncor image) and push to a second ECR repo.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${SCRIPT_DIR}/../common/activate.sh"

SM_REPO="${PROJECT}/motioncor-sm-async"
SM_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_DEFAULT_REGION}.amazonaws.com/${SM_REPO}"

if ! aws ecr describe-repositories --repository-names "$SM_REPO" >/dev/null 2>&1; then
  aws ecr create-repository --repository-name "$SM_REPO" --image-scanning-configuration scanOnPush=true \
    --tags ${TAGS_CLI} >/dev/null
fi

aws ecr get-login-password --region "$AWS_DEFAULT_REGION" \
  | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_DEFAULT_REGION}.amazonaws.com"

cd "$SCRIPT_DIR"
docker build --platform=linux/amd64 \
  --build-arg "BASE_IMAGE=${ECR_URI}:latest" \
  -t "${SM_URI}:latest" \
  -f ./Dockerfile \
  .

docker push "${SM_URI}:latest"
echo "Pushed: ${SM_URI}:latest"
