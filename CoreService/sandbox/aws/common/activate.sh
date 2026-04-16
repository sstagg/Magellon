# Source this in every shell before running any script:
#   source common/activate.sh
#
# Loads .env (creds), exports shared config, verifies identity.

set -a
# .env lives at the project root (..  from common/)
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOT="${SCRIPT_DIR}/.."
if [ -f "${ROOT}/.env" ]; then
  source "${ROOT}/.env"
else
  echo "ERROR: ${ROOT}/.env not found. Copy from .env.example and fill in creds." >&2
  return 1 2>/dev/null || exit 1
fi
source "${SCRIPT_DIR}/config.sh"
set +a

# Verify
ID=$(aws sts get-caller-identity --query Arn --output text 2>&1)
if [[ "$ID" == *"error"* ]] || [[ "$ID" == *"Unable"* ]]; then
  echo "ERROR: AWS creds invalid or expired. Refresh .env." >&2
  echo "       $ID" >&2
  return 1 2>/dev/null || exit 1
fi
echo "AWS  : $ID"
echo "Region: $AWS_DEFAULT_REGION"
echo "Proj : $PROJECT"
