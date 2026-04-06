"""
Test Row-Level Security for webapp endpoints.

Tests that endpoints in webapp_controller.py properly enforce
session-level permissions using Casbin.
"""

import pytest
from uuid import uuid4, UUID
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from services.casbin_service import CasbinService
from models.sqlalchemy_models import Msession, Image, SysSecUser, SysSecRole
from database import get_db


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def db():
    """Database session fixture"""
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def admin_user(db: Session):
    """Create admin user with wildcard session access"""
    user = SysSecUser(
        oid=uuid4(),
        USERNAME="admin_test",
        PASSWORD="hashed_password"
    )
    db.add(user)
    db.commit()

    # Grant admin role
    CasbinService.add_role_for_user(str(user.oid), "Administrator")
    CasbinService.add_permission_for_role("Administrator", "msession:*", "*", "allow")

    yield user

    # Cleanup
    CasbinService.clear_policy()
    db.delete(user)
    db.commit()


@pytest.fixture
def regular_user(db: Session):
    """Create regular user with no initial permissions"""
    user = SysSecUser(
        oid=uuid4(),
        USERNAME="jack_test",
        PASSWORD="hashed_password"
    )
    db.add(user)
    db.commit()

    # Grant researcher role (but no specific permissions yet)
    CasbinService.add_role_for_user(str(user.oid), "Researcher")

    yield user

    # Cleanup
    CasbinService.clear_policy()
    db.delete(user)
    db.commit()


@pytest.fixture
def test_sessions(db: Session):
    """Create test sessions"""
    session_a = Msession(
        oid=uuid4(),
        name="TEST_SESSION_A",
        description="Test session A for RLS"
    )
    session_b = Msession(
        oid=uuid4(),
        name="TEST_SESSION_B",
        description="Test session B for RLS"
    )

    db.add(session_a)
    db.add(session_b)
    db.commit()

    yield {"session_a": session_a, "session_b": session_b}

    # Cleanup
    db.delete(session_a)
    db.delete(session_b)
    db.commit()


@pytest.fixture
def test_images(db: Session, test_sessions):
    """Create test images in both sessions"""
    session_a = test_sessions["session_a"]
    session_b = test_sessions["session_b"]

    # Images in session A
    image_a1 = Image(
        oid=uuid4(),
        name="TEST_SESSION_A_image1.mrc",
        session_id=session_a.oid,
        magnification=50000,
        pixel_size=1.0e-10,
        binning_x=1
    )
    image_a2 = Image(
        oid=uuid4(),
        name="TEST_SESSION_A_image2.mrc",
        session_id=session_a.oid,
        magnification=50000,
        pixel_size=1.0e-10,
        binning_x=1
    )

    # Images in session B
    image_b1 = Image(
        oid=uuid4(),
        name="TEST_SESSION_B_image1.mrc",
        session_id=session_b.oid,
        magnification=75000,
        pixel_size=0.8e-10,
        binning_x=1
    )

    db.add_all([image_a1, image_a2, image_b1])
    db.commit()

    yield {
        "session_a": [image_a1, image_a2],
        "session_b": [image_b1]
    }

    # Cleanup
    db.delete(image_a1)
    db.delete(image_a2)
    db.delete(image_b1)
    db.commit()


def create_auth_token(user_id: UUID) -> str:
    """Helper to create JWT token for user"""
    from controllers.security.authentication import create_access_token
    return create_access_token(data={"sub": str(user_id)})


class TestGetImagesRLS:
    """Test GET /images endpoint with RLS"""

    def test_admin_can_access_all_sessions(self, client, admin_user, test_sessions, test_images):
        """Admin with wildcard permission can access any session"""
        token = create_auth_token(admin_user.oid)
        session_a = test_sessions["session_a"]

        response = client.get(
            f"/images?session_name={session_a.name}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2  # 2 images in session A
        assert all(img["session_id"] == str(session_a.oid) for img in data["result"])

    def test_user_can_access_granted_session(self, client, db, regular_user, test_sessions, test_images):
        """User can access session they have permission for"""
        token = create_auth_token(regular_user.oid)
        session_a = test_sessions["session_a"]

        # Grant access to session A
        CasbinService.add_permission_for_role(
            "Researcher",
            f"msession:{session_a.oid}",
            "read",
            "allow"
        )

        response = client.get(
            f"/images?session_name={session_a.name}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2
        assert all(img["session_id"] == str(session_a.oid) for img in data["result"])

    def test_user_cannot_access_denied_session(self, client, db, regular_user, test_sessions, test_images):
        """User CANNOT access session they don't have permission for"""
        token = create_auth_token(regular_user.oid)
        session_a = test_sessions["session_a"]
        session_b = test_sessions["session_b"]

        # Grant access to session A ONLY
        CasbinService.add_permission_for_role(
            "Researcher",
            f"msession:{session_a.oid}",
            "read",
            "allow"
        )

        # Try to access session B (should fail)
        response = client.get(
            f"/images?session_name={session_b.name}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403  # Forbidden
        assert "Access denied" in response.json()["detail"]

    def test_user_with_no_permissions_denied(self, client, regular_user, test_sessions):
        """User with no permissions is denied access"""
        token = create_auth_token(regular_user.oid)
        session_a = test_sessions["session_a"]

        response = client.get(
            f"/images?session_name={session_a.name}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]


class TestGetImageByNameRLS:
    """Test GET /images/{image_name} endpoint with RLS"""

    def test_admin_can_access_any_image(self, client, admin_user, test_images):
        """Admin can access images from any session"""
        token = create_auth_token(admin_user.oid)
        image_a1 = test_images["session_a"][0]

        response = client.get(
            f"/images/{image_a1.name}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["result"]["name"] == image_a1.name
        assert data["result"]["oid"] == str(image_a1.oid)

    def test_user_can_access_image_from_granted_session(self, client, db, regular_user, test_sessions, test_images):
        """User can access image if they have permission for its session"""
        token = create_auth_token(regular_user.oid)
        session_a = test_sessions["session_a"]
        image_a1 = test_images["session_a"][0]

        # Grant access to session A
        CasbinService.add_permission_for_role(
            "Researcher",
            f"msession:{session_a.oid}",
            "read",
            "allow"
        )

        response = client.get(
            f"/images/{image_a1.name}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["result"]["name"] == image_a1.name

    def test_user_cannot_access_image_from_denied_session(self, client, db, regular_user, test_sessions, test_images):
        """User CANNOT access image from session they don't have permission for"""
        token = create_auth_token(regular_user.oid)
        session_a = test_sessions["session_a"]
        image_b1 = test_images["session_b"][0]  # Image from session B

        # Grant access to session A ONLY
        CasbinService.add_permission_for_role(
            "Researcher",
            f"msession:{session_a.oid}",
            "read",
            "allow"
        )

        # Try to access image from session B (should fail)
        response = client.get(
            f"/images/{image_b1.name}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]


class TestGetSessionMagsRLS:
    """Test GET /session_mags endpoint with RLS"""

    def test_admin_can_get_mags_for_any_session(self, client, admin_user, test_sessions, test_images):
        """Admin can get magnifications for any session"""
        token = create_auth_token(admin_user.oid)
        session_a = test_sessions["session_a"]

        response = client.get(
            f"/session_mags?session_name={session_a.name}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        mags = response.json()
        assert isinstance(mags, list)
        assert 50000 in mags  # Our test images have 50000 magnification

    def test_user_can_get_mags_for_granted_session(self, client, db, regular_user, test_sessions, test_images):
        """User can get magnifications if they have access to session"""
        token = create_auth_token(regular_user.oid)
        session_a = test_sessions["session_a"]

        # Grant access to session A
        CasbinService.add_permission_for_role(
            "Researcher",
            f"msession:{session_a.oid}",
            "read",
            "allow"
        )

        response = client.get(
            f"/session_mags?session_name={session_a.name}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        mags = response.json()
        assert 50000 in mags

    def test_user_cannot_get_mags_for_denied_session(self, client, db, regular_user, test_sessions, test_images):
        """User CANNOT get magnifications for session they don't have access to"""
        token = create_auth_token(regular_user.oid)
        session_a = test_sessions["session_a"]
        session_b = test_sessions["session_b"]

        # Grant access to session A ONLY
        CasbinService.add_permission_for_role(
            "Researcher",
            f"msession:{session_a.oid}",
            "read",
            "allow"
        )

        # Try to access session B magnifications (should fail)
        response = client.get(
            f"/session_mags?session_name={session_b.name}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]


class TestRLSFilteringIntegration:
    """Integration tests for RLS filtering"""

    def test_rls_filter_clause_restricts_results(self, client, db, regular_user, test_sessions, test_images):
        """
        Integration test: Filter clause prevents users from seeing
        unauthorized data even when querying their authorized session.
        """
        token = create_auth_token(regular_user.oid)
        session_a = test_sessions["session_a"]

        # Grant access to session A only
        CasbinService.add_permission_for_role(
            "Researcher",
            f"msession:{session_a.oid}",
            "read",
            "allow"
        )

        # Query session A (should succeed)
        response = client.get(
            f"/images?session_name={session_a.name}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify only session A images are returned
        for img in data["result"]:
            assert img["session_id"] == str(session_a.oid)
            # Verify NOT from session B
            assert img["session_id"] != str(test_sessions["session_b"].oid)

    def test_pagination_respects_rls(self, client, db, regular_user, test_sessions, test_images):
        """Pagination counts and offsets respect RLS filtering"""
        token = create_auth_token(regular_user.oid)
        session_a = test_sessions["session_a"]

        # Grant access to session A
        CasbinService.add_permission_for_role(
            "Researcher",
            f"msession:{session_a.oid}",
            "read",
            "allow"
        )

        # Query with pagination
        response = client.get(
            f"/images?session_name={session_a.name}&page=1&pageSize=1",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Should have 2 total, but only 1 per page
        assert data["total_count"] == 2
        assert len(data["result"]) == 1
        assert data["next_page"] == 2


# Run tests with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
