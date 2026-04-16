# Activating Cost Allocation Tags

Once, per account, someone with access to the **Billing console** must activate our user-defined tags so they appear in Cost Explorer and budgets can filter by them. This is a one-time manual step AWS does not expose via the CLI for the payer org.

## Steps

1. Sign in as an account that can see Billing (may require the FSU payer-account admin, not the SSO admin role).
2. Open **Billing and Cost Management** → **Cost allocation tags** → **User-defined cost allocation tags**.
3. Find and **activate** the following tag keys:
   - `Project`
   - `Owner`
   - `CostCenter`
4. Save.

## When it takes effect

- Budgets scoped to `Project=magellon-gpu-eval` start filtering correctly ~24h after activation.
- Cost Explorer grouping by Project works ~24h after activation.
- Until then, our budget (`common/01-setup-budget.sh`) runs *unfiltered* as a safety net — it'll alert if *any* project spend exceeds $20.

## If you can't activate

You can still run everything — tags still apply to each resource and are visible in the Resource Groups Tagging API (`common/tag-audit.sh` uses this, not cost data). You just won't get tag-filtered cost reporting until activation.
