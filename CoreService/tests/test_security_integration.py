"""
Comprehensive Security Integration Tests

This test suite validates the entire security system end-to-end:
1. Creates test users with different roles
2. Creates test sessions and images
3. Grants session access via object permissions with criteria
4. Syncs permissions to Casbin
5. Executes queries as different users
6. Validates results are correctly filtered by Row-Level Security

Run with: pytest tests/test_security_integration.py -v -s
"""

import pytest
from uuid import uuid4, UUID
from sqlalchemy.orm import Session
from datetime import datetime

from database import session_local, engine
from models.sqlalchemy_models import (
    SysSecUser, SysSecRole, SysSecUserRole,
    SysSecTypePermission, SysSecObjectPermission,
    Msession, Image
)
from services.casbin_service import CasbinService
from services.security.criteria_parser_service import CriteriaParserService
from core.sqlalchemy_row_level_security import (
    apply_row_level_security,
    check_session_access,
    get_accessible_sessions_for_user,
    get_session_filter_clause
)
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== Fixtures ====================

@pytest.fixture(scope="function")
def db():
    """Provide a clean database session for each test"""
    session = session_local()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture(scope="function")
def cleanup_test_data(db: Session):
    """Clean up test data after each test"""
    yield

    # Clean up in reverse order of dependencies
    try:
        # Delete test images
        db.query(Image).filter(Image.frame_name.like('test_image_%')).delete(synchronize_session=False)

        # Delete test sessions
        db.query(Msession).filter(Msession.name.like('test_session_%')).delete(synchronize_session=False)

        # Delete test object permissions
        db.query(SysSecObjectPermission).filter(
            SysSecObjectPermission.Criteria.like('%test_session_%')
        ).delete(synchronize_session=False)

        # Delete test type permissions
        db.query(SysSecTypePermission).filter(
            SysSecTypePermission.TargetType == 'TestEntity'
        ).delete(synchronize_session=False)

        # Delete test user-role assignments
        db.query(SysSecUserRole).filter(
            SysSecUserRole.People.in_(
                db.query(SysSecUser.oid).filter(SysSecUser.USERNAME.like('test_user_%'))
            )
        ).delete(synchronize_session=False)

        # Delete test users
        db.query(SysSecUser).filter(SysSecUser.USERNAME.like('test_user_%')).delete(synchronize_session=False)

        # Delete test roles
        db.query(SysSecRole).filter(SysSecRole.Name.like('test_role_%')).delete(synchronize_session=False)

        db.commit()
        logger.info("Test data cleaned up successfully")
    except Exception as e:
        logger.error(f"Error cleaning up test data: {e}")
        db.rollback()


@pytest.fixture
def test_users(db: Session):
    """Create test users with different roles"""
    # Create test roles
    researcher_role = SysSecRole(
        Oid=uuid4(),
        Name='test_role_researcher',
        IsAdministrative=0,
        CanEditModel=0,
        PermissionPolicy=0
    )
    admin_role = SysSecRole(
        Oid=uuid4(),
        Name='test_role_admin',
        IsAdministrative=1,
        CanEditModel=1,
        PermissionPolicy=1
    )
    db.add(researcher_role)
    db.add(admin_role)
    db.commit()

    # Create test users directly
    alice = SysSecUser(
        oid=uuid4(),
        USERNAME='test_user_alice',
        PASSWORD='hashed_password',
        ACTIVE=True,
        created_date=datetime.utcnow()
    )

    bob = SysSecUser(
        oid=uuid4(),
        USERNAME='test_user_bob',
        PASSWORD='hashed_password',
        ACTIVE=True,
        created_date=datetime.utcnow()
    )

    charlie = SysSecUser(
        oid=uuid4(),
        USERNAME='test_user_charlie',
        PASSWORD='hashed_password',
        ACTIVE=True,
        created_date=datetime.utcnow()
    )

    admin = SysSecUser(
        oid=uuid4(),
        USERNAME='test_user_admin',
        PASSWORD='hashed_password',
        ACTIVE=True,
        created_date=datetime.utcnow()
    )

    db.add_all([alice, bob, charlie, admin])
    db.commit()

    # Assign roles
    db.add(SysSecUserRole(oid=uuid4(), People=alice.oid, Roles=researcher_role.Oid))
    db.add(SysSecUserRole(oid=uuid4(), People=bob.oid, Roles=researcher_role.Oid))
    db.add(SysSecUserRole(oid=uuid4(), People=charlie.oid, Roles=researcher_role.Oid))
    db.add(SysSecUserRole(oid=uuid4(), People=admin.oid, Roles=admin_role.Oid))
    db.commit()

    # Sync roles to Casbin
    CasbinService.initialize()
    CasbinService.add_role_for_user(str(alice.oid), 'test_role_researcher')
    CasbinService.add_role_for_user(str(bob.oid), 'test_role_researcher')
    CasbinService.add_role_for_user(str(charlie.oid), 'test_role_researcher')
    CasbinService.add_role_for_user(str(admin.oid), 'test_role_admin')

    logger.info(f"Created test users: Alice={alice.oid}, Bob={bob.oid}, Charlie={charlie.oid}, Admin={admin.oid}")

    return {
        'alice': alice,
        'bob': bob,
        'charlie': charlie,
        'admin': admin,
        'researcher_role': researcher_role,
        'admin_role': admin_role
    }


@pytest.fixture
def test_sessions(db: Session):
    """Create test microscopy sessions"""
    session_a = Msession(
        oid=uuid4(),
        name='test_session_A'
    )

    session_b = Msession(
        oid=uuid4(),
        name='test_session_B'
    )

    session_c = Msession(
        oid=uuid4(),
        name='test_session_C'
    )

    session_shared = Msession(
        oid=uuid4(),
        name='test_session_shared'
    )

    db.add_all([session_a, session_b, session_c, session_shared])
    db.commit()

    logger.info(f"Created test sessions: A={session_a.oid}, B={session_b.oid}, C={session_c.oid}, Shared={session_shared.oid}")

    return {
        'session_a': session_a,
        'session_b': session_b,
        'session_c': session_c,
        'session_shared': session_shared
    }


@pytest.fixture
def test_images(db: Session, test_sessions):
    """Create test images in each session"""
    images = []

    # Session A images (3 images)
    for i in range(3):
        img = Image(
            oid=uuid4(),
            frame_name=f'test_image_A_{i}.mrc',
            session_id=test_sessions['session_a'].oid
        )
        images.append(img)

    # Session B images (2 images)
    for i in range(2):
        img = Image(
            oid=uuid4(),
            frame_name=f'test_image_B_{i}.mrc',
            session_id=test_sessions['session_b'].oid
        )
        images.append(img)

    # Session C images (4 images)
    for i in range(4):
        img = Image(
            oid=uuid4(),
            frame_name=f'test_image_C_{i}.mrc',
            session_id=test_sessions['session_c'].oid
        )
        images.append(img)

    # Shared session images (5 images)
    for i in range(5):
        img = Image(
            oid=uuid4(),
            frame_name=f'test_image_shared_{i}.mrc',
            session_id=test_sessions['session_shared'].oid
        )
        images.append(img)

    db.add_all(images)
    db.commit()

    logger.info(f"Created {len(images)} test images across 4 sessions")

    return images


# ==================== Tests ====================

class TestBasicPermissionSetup:
    """Test basic permission setup and Casbin integration"""

    def test_users_created_successfully(self, db: Session, test_users, cleanup_test_data):
        """Verify test users are created with correct roles"""
        alice = test_users['alice']

        # Verify user exists
        user = db.query(SysSecUser).filter(SysSecUser.oid == alice.oid).first()
        assert user is not None
        assert user.USERNAME == 'test_user_alice'

        # Verify role assignment
        user_role = db.query(SysSecUserRole).filter(
            SysSecUserRole.People == alice.oid
        ).first()
        assert user_role is not None

        # Verify Casbin role
        roles = CasbinService.get_roles_for_user(str(alice.oid))
        assert 'test_role_researcher' in roles

        logger.info(f"✓ Alice has roles: {roles}")

    def test_sessions_created_successfully(self, db: Session, test_sessions, cleanup_test_data):
        """Verify test sessions are created"""
        session_a = test_sessions['session_a']

        session = db.query(Msession).filter(Msession.oid == session_a.oid).first()
        assert session is not None
        assert session.name == 'test_session_A'

        logger.info(f"✓ Session A created: {session.oid}")

    def test_images_created_successfully(self, db: Session, test_images, test_sessions, cleanup_test_data):
        """Verify test images are created in correct sessions"""
        session_a_id = test_sessions['session_a'].oid

        images_in_a = db.query(Image).filter(Image.session_id == session_a_id).count()
        assert images_in_a == 3

        logger.info(f"✓ Session A has {images_in_a} images")


class TestObjectPermissionCriteria:
    """Test object permissions with criteria parsing"""

    def test_grant_alice_access_to_session_a(
        self, db: Session, test_users, test_sessions, cleanup_test_data
    ):
        """Grant Alice access to Session A using criteria"""
        alice = test_users['alice']
        session_a = test_sessions['session_a']
        researcher_role = test_users['researcher_role']

        # Create type permission for Msession
        type_perm = SysSecTypePermission(
            Oid=uuid4(),
            Role=researcher_role.Oid,
            TargetType='Msession',
            ReadState=1,
            WriteState=0,
            CreateState=0,
            DeleteState=0,
            NavigateState=1
        )
        db.add(type_perm)
        db.commit()

        # Create object permission with criteria
        criteria = f"[oid] = '{session_a.oid}'"
        obj_perm = SysSecObjectPermission(
            oid=uuid4(),
            TypePermissionObject=type_perm.Oid,
            Criteria=criteria,
            ReadState=1,
            WriteState=0,
            DeleteState=0,
            NavigateState=1
        )
        db.add(obj_perm)
        db.commit()

        # Parse criteria and sync to Casbin
        resources = CriteriaParserService.parse_criteria(criteria, 'Msession')
        assert len(resources) == 1
        assert resources[0] == f"msession:{session_a.oid}"

        # Add to Casbin
        for resource in resources:
            CasbinService.add_permission_for_role(
                'test_role_researcher',
                resource,
                'read',
                'allow'
            )

        # Verify permission in Casbin
        has_access = CasbinService.enforce(str(alice.oid), f"msession:{session_a.oid}", "read")
        assert has_access is True

        logger.info(f"✓ Alice granted access to Session A via criteria: {criteria}")
        logger.info(f"✓ Casbin enforces: {has_access}")

    def test_grant_bob_access_to_multiple_sessions(
        self, db: Session, test_users, test_sessions, cleanup_test_data
    ):
        """Grant Bob access to Session B and Shared Session using IN clause"""
        bob = test_users['bob']
        session_b = test_sessions['session_b']
        session_shared = test_sessions['session_shared']
        researcher_role = test_users['researcher_role']

        # Create type permission
        type_perm = SysSecTypePermission(
            Oid=uuid4(),
            Role=researcher_role.Oid,
            TargetType='Msession',
            ReadState=1,
            WriteState=0,
            CreateState=0,
            DeleteState=0,
            NavigateState=1
        )
        db.add(type_perm)
        db.commit()

        # Create object permission with IN clause
        criteria = f"[oid] IN ('{session_b.oid}', '{session_shared.oid}')"
        obj_perm = SysSecObjectPermission(
            oid=uuid4(),
            TypePermissionObject=type_perm.Oid,
            Criteria=criteria,
            ReadState=1,
            WriteState=0,
            DeleteState=0,
            NavigateState=1
        )
        db.add(obj_perm)
        db.commit()

        # Parse criteria and sync to Casbin
        resources = CriteriaParserService.parse_criteria(criteria, 'Msession')
        assert len(resources) == 2

        for resource in resources:
            CasbinService.add_permission_for_role(
                'test_role_researcher',
                resource,
                'read',
                'allow'
            )

        # Verify Bob has access to both sessions
        has_access_b = CasbinService.enforce(str(bob.oid), f"msession:{session_b.oid}", "read")
        has_access_shared = CasbinService.enforce(str(bob.oid), f"msession:{session_shared.oid}", "read")

        assert has_access_b is True
        assert has_access_shared is True

        logger.info(f"✓ Bob granted access to 2 sessions via IN clause")
        logger.info(f"✓ Bob can access Session B: {has_access_b}")
        logger.info(f"✓ Bob can access Shared Session: {has_access_shared}")

    def test_charlie_has_no_access(
        self, db: Session, test_users, test_sessions, cleanup_test_data
    ):
        """Verify Charlie has no access to any session (no permissions granted)"""
        charlie = test_users['charlie']
        session_a = test_sessions['session_a']
        session_b = test_sessions['session_b']
        session_c = test_sessions['session_c']

        # Charlie should have no access to any session
        has_access_a = CasbinService.enforce(str(charlie.oid), f"msession:{session_a.oid}", "read")
        has_access_b = CasbinService.enforce(str(charlie.oid), f"msession:{session_b.oid}", "read")
        has_access_c = CasbinService.enforce(str(charlie.oid), f"msession:{session_c.oid}", "read")

        assert has_access_a is False
        assert has_access_b is False
        assert has_access_c is False

        logger.info(f"✓ Charlie has no access to any session (as expected)")


class TestRowLevelSecurityFiltering:
    """Test Row-Level Security automatic query filtering"""

    def test_alice_sees_only_session_a_images(
        self, db: Session, test_users, test_sessions, test_images, cleanup_test_data
    ):
        """Alice should only see images from Session A after RLS is applied"""
        alice = test_users['alice']
        session_a = test_sessions['session_a']

        # Grant Alice access to Session A
        CasbinService.add_permission_for_role(
            'test_role_researcher',
            f"msession:{session_a.oid}",
            'read',
            'allow'
        )

        # Apply RLS to database session
        apply_row_level_security(db, alice.oid)

        # Query all images - should only get Session A images
        images = db.query(Image).filter(Image.frame_name.like('test_image_%')).all()

        # Verify only Session A images (3 images)
        assert len(images) == 3
        for img in images:
            assert img.session_id == session_a.oid
            assert 'test_image_A_' in img.frame_name

        logger.info(f"✓ Alice sees {len(images)} images (only from Session A)")
        logger.info(f"  Images: {[img.frame_name for img in images]}")

    def test_bob_sees_multiple_session_images(
        self, db: Session, test_users, test_sessions, test_images, cleanup_test_data
    ):
        """Bob should see images from Session B and Shared Session"""
        bob = test_users['bob']
        session_b = test_sessions['session_b']
        session_shared = test_sessions['session_shared']

        # Grant Bob access to Session B and Shared
        CasbinService.add_permission_for_role(
            'test_role_researcher',
            f"msession:{session_b.oid}",
            'read',
            'allow'
        )
        CasbinService.add_permission_for_role(
            'test_role_researcher',
            f"msession:{session_shared.oid}",
            'read',
            'allow'
        )

        # Apply RLS
        apply_row_level_security(db, bob.oid)

        # Query all images
        images = db.query(Image).filter(Image.frame_name.like('test_image_%')).all()

        # Should see 2 (Session B) + 5 (Shared) = 7 images
        assert len(images) == 7

        session_ids = {img.session_id for img in images}
        assert session_b.oid in session_ids
        assert session_shared.oid in session_ids

        logger.info(f"✓ Bob sees {len(images)} images from 2 sessions")
        logger.info(f"  Session B images: {sum(1 for img in images if img.session_id == session_b.oid)}")
        logger.info(f"  Shared images: {sum(1 for img in images if img.session_id == session_shared.oid)}")

    def test_charlie_sees_no_images(
        self, db: Session, test_users, test_sessions, test_images, cleanup_test_data
    ):
        """Charlie should see no images (no permissions granted)"""
        charlie = test_users['charlie']

        # Apply RLS (Charlie has no permissions)
        apply_row_level_security(db, charlie.oid)

        # Query all images
        images = db.query(Image).filter(Image.frame_name.like('test_image_%')).all()

        # Should see 0 images
        assert len(images) == 0

        logger.info(f"✓ Charlie sees {len(images)} images (no permissions)")

    def test_admin_sees_all_images(
        self, db: Session, test_users, test_sessions, test_images, cleanup_test_data
    ):
        """Admin should see all images (wildcard access)"""
        admin = test_users['admin']

        # Grant admin wildcard access
        CasbinService.add_permission_for_role(
            'test_role_admin',
            'msession:*',
            'read',
            'allow'
        )

        # Apply RLS
        apply_row_level_security(db, admin.oid)

        # Query all images
        images = db.query(Image).filter(Image.frame_name.like('test_image_%')).all()

        # Should see all 14 images (3 + 2 + 4 + 5)
        assert len(images) == 14

        logger.info(f"✓ Admin sees {len(images)} images (wildcard access)")


class TestManualSQLFiltering:
    """Test manual SQL filtering with get_session_filter_clause"""

    def test_alice_raw_sql_filtering(
        self, db: Session, test_users, test_sessions, test_images, cleanup_test_data
    ):
        """Test raw SQL filtering for Alice"""
        alice = test_users['alice']
        session_a = test_sessions['session_a']

        # Grant Alice access to Session A
        CasbinService.add_permission_for_role(
            'test_role_researcher',
            f"msession:{session_a.oid}",
            'read',
            'allow'
        )

        # Get filter clause
        filter_clause, filter_params = get_session_filter_clause(alice.oid, column_name='session_id')

        # Verify filter is generated
        assert filter_clause != ""
        assert 'session_id' in filter_clause
        assert 'accessible_sessions' in filter_params

        # Verify Alice's accessible sessions
        accessible = filter_params['accessible_sessions']
        assert str(session_a.oid) in accessible

        logger.info(f"✓ Alice filter clause: {filter_clause}")
        logger.info(f"✓ Alice accessible sessions: {accessible}")

    def test_charlie_raw_sql_returns_empty(
        self, db: Session, test_users, cleanup_test_data
    ):
        """Test that Charlie gets empty filter (no access)"""
        charlie = test_users['charlie']

        # Get filter clause (Charlie has no permissions)
        filter_clause, filter_params = get_session_filter_clause(charlie.oid, column_name='session_id')

        # Should get filter with empty tuple
        assert filter_clause != ""
        assert filter_params['accessible_sessions'] == tuple()

        logger.info(f"✓ Charlie filter returns empty: {filter_params}")


class TestAccessCheckUtilities:
    """Test utility functions for access checking"""

    def test_check_session_access(
        self, db: Session, test_users, test_sessions, cleanup_test_data
    ):
        """Test check_session_access utility"""
        alice = test_users['alice']
        bob = test_users['bob']
        session_a = test_sessions['session_a']
        session_b = test_sessions['session_b']

        # Grant Alice access to Session A
        CasbinService.add_permission_for_role(
            'test_role_researcher',
            f"msession:{session_a.oid}",
            'read',
            'allow'
        )

        # Check access
        alice_can_access_a = check_session_access(alice.oid, session_a.oid, 'read')
        alice_can_access_b = check_session_access(alice.oid, session_b.oid, 'read')
        bob_can_access_a = check_session_access(bob.oid, session_a.oid, 'read')

        assert alice_can_access_a is True
        assert alice_can_access_b is False
        assert bob_can_access_a is False

        logger.info(f"✓ Alice can access Session A: {alice_can_access_a}")
        logger.info(f"✓ Alice can access Session B: {alice_can_access_b}")
        logger.info(f"✓ Bob can access Session A: {bob_can_access_a}")

    def test_get_accessible_sessions(
        self, db: Session, test_users, test_sessions, cleanup_test_data
    ):
        """Test get_accessible_sessions_for_user utility"""
        alice = test_users['alice']
        bob = test_users['bob']
        session_a = test_sessions['session_a']
        session_b = test_sessions['session_b']
        session_shared = test_sessions['session_shared']

        # Grant permissions
        CasbinService.add_permission_for_role(
            'test_role_researcher',
            f"msession:{session_a.oid}",
            'read',
            'allow'
        )
        CasbinService.add_permission_for_role(
            'test_role_researcher',
            f"msession:{session_b.oid}",
            'read',
            'allow'
        )
        CasbinService.add_permission_for_role(
            'test_role_researcher',
            f"msession:{session_shared.oid}",
            'read',
            'allow'
        )

        # Get accessible sessions
        alice_sessions = get_accessible_sessions_for_user(alice.oid)
        bob_sessions = get_accessible_sessions_for_user(bob.oid)

        # Alice and Bob should both have access to all 3 sessions
        # (because they share the same role)
        assert len(alice_sessions) >= 3
        assert str(session_a.oid) in alice_sessions

        logger.info(f"✓ Alice accessible sessions: {len(alice_sessions)}")
        logger.info(f"✓ Bob accessible sessions: {len(bob_sessions)}")


class TestComplexScenarios:
    """Test complex real-world scenarios"""

    def test_scenario_shared_session_multiple_users(
        self, db: Session, test_users, test_sessions, test_images, cleanup_test_data
    ):
        """
        Scenario: Session is shared between Alice and Bob
        - Alice has access to Session A and Shared
        - Bob has access to Session B and Shared
        - Both should see the shared session images
        """
        alice = test_users['alice']
        bob = test_users['bob']
        session_a = test_sessions['session_a']
        session_b = test_sessions['session_b']
        session_shared = test_sessions['session_shared']

        # Grant permissions
        # Alice: Session A + Shared
        CasbinService.add_permission_for_role(
            'test_role_researcher',
            f"msession:{session_a.oid}",
            'read',
            'allow'
        )
        CasbinService.add_permission_for_role(
            'test_role_researcher',
            f"msession:{session_shared.oid}",
            'read',
            'allow'
        )

        # Bob: Session B + Shared (using different role instance)
        # Create Bob's specific permissions
        bob_role = SysSecRole(
            Oid=uuid4(),
            Name='test_role_bob_specific',
            IsAdministrative=0,
            CanEditModel=0,
            PermissionPolicy=0
        )
        db.add(bob_role)
        db.commit()

        # Assign Bob to his specific role
        db.add(SysSecUserRole(oid=uuid4(), People=bob.oid, Roles=bob_role.Oid))
        db.commit()

        CasbinService.add_role_for_user(str(bob.oid), 'test_role_bob_specific')
        CasbinService.add_permission_for_role(
            'test_role_bob_specific',
            f"msession:{session_b.oid}",
            'read',
            'allow'
        )
        CasbinService.add_permission_for_role(
            'test_role_bob_specific',
            f"msession:{session_shared.oid}",
            'read',
            'allow'
        )

        # Test Alice's view
        db_alice = session_local()
        apply_row_level_security(db_alice, alice.oid)
        alice_images = db_alice.query(Image).filter(Image.frame_name.like('test_image_%')).all()
        db_alice.close()

        # Alice should see: 3 (Session A) + 5 (Shared) = 8 images
        assert len(alice_images) == 8

        # Test Bob's view
        db_bob = session_local()
        apply_row_level_security(db_bob, bob.oid)
        bob_images = db_bob.query(Image).filter(Image.frame_name.like('test_image_%')).all()
        db_bob.close()

        # Bob should see: 2 (Session B) + 5 (Shared) = 7 images
        assert len(bob_images) == 7

        # Verify both see the shared images
        alice_shared_images = [img for img in alice_images if img.session_id == session_shared.oid]
        bob_shared_images = [img for img in bob_images if img.session_id == session_shared.oid]

        assert len(alice_shared_images) == 5
        assert len(bob_shared_images) == 5

        logger.info(f"✓ Alice sees {len(alice_images)} images (Session A + Shared)")
        logger.info(f"✓ Bob sees {len(bob_images)} images (Session B + Shared)")
        logger.info(f"✓ Both see {len(alice_shared_images)} shared images")

    def test_scenario_permission_revocation(
        self, db: Session, test_users, test_sessions, test_images, cleanup_test_data
    ):
        """
        Scenario: Permission is granted then revoked
        - Alice initially has access to Session A
        - Permission is revoked
        - Alice should no longer see Session A images
        """
        alice = test_users['alice']
        session_a = test_sessions['session_a']

        # Grant permission
        CasbinService.add_permission_for_role(
            'test_role_researcher',
            f"msession:{session_a.oid}",
            'read',
            'allow'
        )

        # Verify Alice can access
        db_before = session_local()
        apply_row_level_security(db_before, alice.oid)
        images_before = db_before.query(Image).filter(Image.frame_name.like('test_image_%')).all()
        db_before.close()

        assert len(images_before) == 3  # Session A images

        # Revoke permission
        CasbinService.remove_policy(
            'test_role_researcher',
            f"msession:{session_a.oid}",
            'read',
            'allow'
        )

        # Verify Alice can no longer access
        db_after = session_local()
        apply_row_level_security(db_after, alice.oid)
        images_after = db_after.query(Image).filter(Image.frame_name.like('test_image_%')).all()
        db_after.close()

        assert len(images_after) == 0  # No access

        logger.info(f"✓ Before revocation: {len(images_before)} images")
        logger.info(f"✓ After revocation: {len(images_after)} images")


# ==================== Summary Test ====================

def test_comprehensive_security_summary(
    db: Session, test_users, test_sessions, test_images, cleanup_test_data
):
    """
    Comprehensive test that validates entire security system:
    1. Create users and sessions
    2. Grant specific permissions via criteria
    3. Sync to Casbin
    4. Execute queries as different users
    5. Validate results
    """
    alice = test_users['alice']
    bob = test_users['bob']
    charlie = test_users['charlie']
    admin = test_users['admin']

    session_a = test_sessions['session_a']
    session_b = test_sessions['session_b']
    session_c = test_sessions['session_c']
    session_shared = test_sessions['session_shared']

    # === SETUP PERMISSIONS ===

    # Alice: Session A
    CasbinService.add_permission_for_role(
        'test_role_researcher',
        f"msession:{session_a.oid}",
        'read',
        'allow'
    )

    # Create Bob-specific role for his permissions
    bob_role = SysSecRole(
        Oid=uuid4(),
        Name='test_role_bob_specific',
        IsAdministrative=0,
        CanEditModel=0,
        PermissionPolicy=0
    )
    db.add(bob_role)
    db.commit()
    db.add(SysSecUserRole(oid=uuid4(), People=bob.oid, Roles=bob_role.Oid))
    db.commit()

    CasbinService.add_role_for_user(str(bob.oid), 'test_role_bob_specific')
    CasbinService.add_permission_for_role(
        'test_role_bob_specific',
        f"msession:{session_b.oid}",
        'read',
        'allow'
    )
    CasbinService.add_permission_for_role(
        'test_role_bob_specific',
        f"msession:{session_shared.oid}",
        'read',
        'allow'
    )

    # Charlie: No permissions

    # Admin: Wildcard
    CasbinService.add_permission_for_role(
        'test_role_admin',
        'msession:*',
        'read',
        'allow'
    )

    # === EXECUTE QUERIES ===

    # Alice query
    db_alice = session_local()
    apply_row_level_security(db_alice, alice.oid)
    alice_images = db_alice.query(Image).filter(Image.frame_name.like('test_image_%')).all()
    db_alice.close()

    # Bob query
    db_bob = session_local()
    apply_row_level_security(db_bob, bob.oid)
    bob_images = db_bob.query(Image).filter(Image.frame_name.like('test_image_%')).all()
    db_bob.close()

    # Charlie query
    db_charlie = session_local()
    apply_row_level_security(db_charlie, charlie.oid)
    charlie_images = db_charlie.query(Image).filter(Image.frame_name.like('test_image_%')).all()
    db_charlie.close()

    # Admin query
    db_admin = session_local()
    apply_row_level_security(db_admin, admin.oid)
    admin_images = db_admin.query(Image).filter(Image.frame_name.like('test_image_%')).all()
    db_admin.close()

    # === VALIDATE RESULTS ===

    # Alice should see 3 images (Session A only)
    assert len(alice_images) == 3
    assert all(img.session_id == session_a.oid for img in alice_images)

    # Bob should see 7 images (Session B: 2 + Shared: 5)
    assert len(bob_images) == 7
    bob_session_ids = {img.session_id for img in bob_images}
    assert session_b.oid in bob_session_ids
    assert session_shared.oid in bob_session_ids

    # Charlie should see 0 images
    assert len(charlie_images) == 0

    # Admin should see all 14 images
    assert len(admin_images) == 14

    # === PRINT SUMMARY ===

    logger.info("\n" + "="*60)
    logger.info("COMPREHENSIVE SECURITY TEST SUMMARY")
    logger.info("="*60)
    logger.info(f"Total test images: 14")
    logger.info(f"  - Session A: 3 images")
    logger.info(f"  - Session B: 2 images")
    logger.info(f"  - Session C: 4 images")
    logger.info(f"  - Shared: 5 images")
    logger.info("")
    logger.info(f"Alice (access to Session A):")
    logger.info(f"  ✓ Sees {len(alice_images)} images (expected: 3)")
    logger.info("")
    logger.info(f"Bob (access to Session B + Shared):")
    logger.info(f"  ✓ Sees {len(bob_images)} images (expected: 7)")
    logger.info("")
    logger.info(f"Charlie (no access):")
    logger.info(f"  ✓ Sees {len(charlie_images)} images (expected: 0)")
    logger.info("")
    logger.info(f"Admin (wildcard access):")
    logger.info(f"  ✓ Sees {len(admin_images)} images (expected: 14)")
    logger.info("="*60)
    logger.info("✓ ALL SECURITY CHECKS PASSED!")
    logger.info("="*60 + "\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
