#!/usr/bin/env bash
# Create a $20 monthly budget for this project. Idempotent: updates if exists.
# Scoped to Project=magellon-gpu-eval tag (only effective after cost tags are activated in the
# billing console — see enable-cost-tags.md). Until then this acts as a whole-account safety net.
#
# Alerts at 50%, 80%, 100% of actual + 100% of forecasted, to $ALERT_EMAIL.

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${SCRIPT_DIR}/activate.sh"

BUDGET_NAME="${PROJECT}"
LIMIT_USD="20"

read -r -d '' BUDGET_JSON <<EOF || true
{
  "BudgetName": "${BUDGET_NAME}",
  "BudgetType": "COST",
  "TimeUnit": "MONTHLY",
  "BudgetLimit": {"Amount": "${LIMIT_USD}", "Unit": "USD"},
  "CostFilters": {"TagKeyValue": ["user:Project\$${PROJECT}"]},
  "CostTypes": {
    "IncludeTax": true, "IncludeSubscription": true, "UseBlended": false,
    "IncludeRefund": false, "IncludeCredit": false, "IncludeUpfront": true,
    "IncludeRecurring": true, "IncludeOtherSubscription": true,
    "IncludeSupport": true, "IncludeDiscount": true, "UseAmortized": false
  }
}
EOF

NOTIF_50='{"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":50,"ThresholdType":"PERCENTAGE","NotificationState":"OK"},"Subscribers":[{"SubscriptionType":"EMAIL","Address":"'${ALERT_EMAIL}'"}]}'
NOTIF_80='{"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":80,"ThresholdType":"PERCENTAGE","NotificationState":"OK"},"Subscribers":[{"SubscriptionType":"EMAIL","Address":"'${ALERT_EMAIL}'"}]}'
NOTIF_100='{"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":100,"ThresholdType":"PERCENTAGE","NotificationState":"OK"},"Subscribers":[{"SubscriptionType":"EMAIL","Address":"'${ALERT_EMAIL}'"}]}'
NOTIF_FC='{"Notification":{"NotificationType":"FORECASTED","ComparisonOperator":"GREATER_THAN","Threshold":100,"ThresholdType":"PERCENTAGE","NotificationState":"OK"},"Subscribers":[{"SubscriptionType":"EMAIL","Address":"'${ALERT_EMAIL}'"}]}'
NOTIFS="[${NOTIF_50},${NOTIF_80},${NOTIF_100},${NOTIF_FC}]"

EXISTING=$(aws budgets describe-budget --account-id "$AWS_ACCOUNT_ID" --budget-name "$BUDGET_NAME" 2>&1 || true)
if echo "$EXISTING" | grep -q NotFoundException; then
  echo "Creating budget '$BUDGET_NAME' (\$${LIMIT_USD}/mo)..."
  aws budgets create-budget --account-id "$AWS_ACCOUNT_ID" \
    --budget "$BUDGET_JSON" \
    --notifications-with-subscribers "$NOTIFS"
  echo "Done. A confirmation email will go to ${ALERT_EMAIL}."
else
  echo "Budget '$BUDGET_NAME' exists — updating limit/filters..."
  aws budgets update-budget --account-id "$AWS_ACCOUNT_ID" --new-budget "$BUDGET_JSON"
  echo "Updated. Notifications left in place."
fi

echo
echo "NOTE: tag-based filtering only works once 'Project' is activated in the billing console."
echo "      See common/enable-cost-tags.md."
