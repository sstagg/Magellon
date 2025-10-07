"""
Script to perform initial sync of policies from sys_sec_* tables to Casbin

Run this:
- After installing Casbin
- After permission schema changes
- Periodically to ensure sync
- When you want to rebuild Casbin policies from scratch

Usage:
    python scripts/sync_policies_to_casbin.py
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import session_local
from services.casbin_policy_sync_service import CasbinPolicySyncService
from services.casbin_service import CasbinService
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Sync all policies from sys_sec_* tables to Casbin"""
    logger.info("")
    logger.info("=" * 80)
    logger.info("  Casbin Policy Synchronization Script")
    logger.info("=" * 80)
    logger.info("")

    db = session_local()

    try:
        # Initialize Casbin
        logger.info("Step 1: Initializing Casbin enforcer...")
        CasbinService.initialize()
        logger.info("✓ Casbin enforcer initialized")
        logger.info("")

        # Show current policy counts
        before_counts = CasbinService.get_policy_count()
        logger.info(f"Current Casbin state:")
        logger.info(f"  - Policies: {before_counts['policies']}")
        logger.info(f"  - Role assignments: {before_counts['role_assignments']}")
        logger.info("")

        # Perform sync
        logger.info("Step 2: Syncing policies from sys_sec_* tables...")
        logger.info("")

        stats = CasbinPolicySyncService.sync_all_policies(db, clear_existing=True)

        logger.info("")
        logger.info("Step 3: Verifying sync...")
        logger.info("")

        # Verify sync
        verification = CasbinPolicySyncService.verify_sync(db)

        logger.info("")
        logger.info("=" * 80)
        logger.info("  Sync Complete!")
        logger.info("=" * 80)
        logger.info("")
        logger.info("Summary:")
        logger.info(f"  ✓ User-Role assignments: {stats['user_roles']}")
        logger.info(f"  ✓ Action permissions: {stats['action_permissions']}")
        logger.info(f"  ✓ Navigation permissions: {stats['navigation_permissions']}")
        logger.info(f"  ✓ Type permissions: {stats['type_permissions']}")
        logger.info(f"  ✓ Total policies: {stats['total_policies']}")
        logger.info("")

        if len(verification['discrepancies']) > 0:
            logger.warning("⚠ Verification found discrepancies:")
            for disc in verification['discrepancies']:
                logger.warning(f"  - {disc}")
            logger.warning("")
            logger.warning("This may be normal if:")
            logger.warning("  - Some permissions are soft-deleted (GCRecord != NULL)")
            logger.warning("  - Type permissions generate multiple policies per row")
        else:
            logger.info("✓ Verification passed - policies match database!")

        logger.info("")
        logger.info("=" * 80)
        logger.info("  Next Steps:")
        logger.info("=" * 80)
        logger.info("")
        logger.info("1. Start your FastAPI application:")
        logger.info("   python -m uvicorn main:app --reload")
        logger.info("")
        logger.info("2. Policies will auto-sync on startup")
        logger.info("")
        logger.info("3. Test permissions:")
        logger.info("   from services.casbin_service import CasbinService")
        logger.info("   CasbinService.enforce(user_id, resource, action)")
        logger.info("")
        logger.info("=" * 80)

    except Exception as e:
        logger.error("")
        logger.error("=" * 80)
        logger.error("  ✗ Sync Failed!")
        logger.error("=" * 80)
        logger.error(f"Error: {e}")
        logger.exception(e)
        logger.error("")
        sys.exit(1)

    finally:
        db.close()


if __name__ == '__main__':
    main()
