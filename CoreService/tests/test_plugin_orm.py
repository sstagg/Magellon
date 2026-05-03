"""Smoke tests for the PM1 ORM additions (alembic 0008).

Pin the SQLAlchemy column shape that alembic migration 0008 declares
+ verify the relationships resolve. No DB session needed — these
test the model module's in-memory shape, catching the
"alembic landed but ORM didn't" or vice versa class of regression.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from models.sqlalchemy_models import (
    Plugin,
    PluginCategoryDefault,
    PluginState,
)


# ---------------------------------------------------------------------------
# Plugin extensions (alembic 0008)
# ---------------------------------------------------------------------------


def test_plugin_has_promoted_catalog_fields():
    """alembic 0008 promotes catalog hot fields from input_json to
    real columns. Pin the names so a future migration can't silently
    drop one."""
    cols = Plugin.__table__.columns
    expected = {
        "manifest_plugin_id", "backend_id", "category",
        "schema_version", "install_method", "install_dir",
        "image_ref", "container_ref", "archive_id",
        "manifest_json", "installed_date",
    }
    missing = expected - set(cols.keys())
    assert not missing, f"Plugin is missing columns: {missing}"


def test_plugin_version_widened_to_64_chars():
    """SemVer with prerelease tags (1.2.3-rc.1+build.42) blows past
    the legacy VARCHAR(10). Pinned at 64."""
    col = Plugin.__table__.columns["version"]
    assert col.type.length == 64


def test_plugin_does_not_have_a_column_called_plugin_id():
    """Reviewer-flagged High #2 from PLUGIN_MANAGER_PLAN.md revision 1:
    a column called ``plugin_id`` would collide with
    ``image_meta_data.plugin_id`` which is already a FK to plugin.oid.
    The new column must be named ``manifest_plugin_id``. Pin so a
    future PR can't silently re-introduce the conflict."""
    cols = Plugin.__table__.columns
    assert "plugin_id" not in cols.keys()
    assert "manifest_plugin_id" in cols.keys()


def test_plugin_manifest_plugin_id_is_indexed():
    """Hot lookup: install pipeline finds existing rows by slug to
    decide upsert-vs-update."""
    col = Plugin.__table__.columns["manifest_plugin_id"]
    assert col.index is True


# ---------------------------------------------------------------------------
# plugin_state table (alembic 0008)
# ---------------------------------------------------------------------------


def test_plugin_state_columns():
    cols = PluginState.__table__.columns
    expected = {"plugin_oid", "enabled", "last_seen_at",
                "last_heartbeat_at", "OptimisticLockField"}
    assert expected.issubset(cols.keys())


def test_plugin_state_enabled_defaults_to_true():
    """Pre-PM1 in-memory shim defaulted to True; the persisted
    version must match so the migration doesn't flip behaviour for
    plugins without an existing row."""
    col = PluginState.__table__.columns["enabled"]
    assert col.nullable is False
    assert col.server_default is not None
    assert "1" in str(col.server_default.arg)


def test_plugin_state_does_not_have_paused_columns():
    """Reviewer-flagged Medium #6 from the plan revision: PM4's
    paused/paused_reason/paused_at/paused_until columns live in
    alembic 0009, NOT here. PM1 ships only the enabled flag so PM1
    can soak independently of pause-design work."""
    cols = PluginState.__table__.columns
    for forbidden in ("paused", "paused_reason", "paused_at", "paused_until"):
        assert forbidden not in cols.keys(), (
            f"{forbidden} belongs in PM4's alembic 0009, not PM1's 0008"
        )


def test_plugin_state_is_keyed_on_plugin_oid_not_string():
    """Reviewer-flagged High #2 fix: PK is plugin_oid (UUID FK to
    plugin.oid), not a string copy of the runtime plugin_id."""
    pk_cols = [c.name for c in PluginState.__table__.columns if c.primary_key]
    assert pk_cols == ["plugin_oid"]


# ---------------------------------------------------------------------------
# plugin_category_default table (alembic 0008)
# ---------------------------------------------------------------------------


def test_plugin_category_default_columns():
    cols = PluginCategoryDefault.__table__.columns
    expected = {"category", "plugin_oid", "set_at", "set_by_user_id"}
    assert expected.issubset(cols.keys())


def test_plugin_category_default_pk_is_category():
    """Reviewer-flagged High #1: at most one default per category;
    PK enforces uniqueness without a separate constraint."""
    pk_cols = [
        c.name
        for c in PluginCategoryDefault.__table__.columns
        if c.primary_key
    ]
    assert pk_cols == ["category"]


def test_plugin_category_default_supports_multi_category_plugins():
    """The whole point of a separate table (vs a boolean on the
    plugin row): multi-category plugins like topaz can be default
    for one category but not another. Verify two rows pointing at
    the same plugin, different categories, both round-trip cleanly
    through the ORM constructor."""
    topaz_oid = uuid.uuid4()

    pick_default = PluginCategoryDefault(
        category="topaz_particle_picking",
        plugin_oid=topaz_oid,
        set_at=datetime.utcnow(),
        set_by_user_id="bkhoshbin",
    )
    denoise_default = PluginCategoryDefault(
        category="micrograph_denoising",
        plugin_oid=topaz_oid,
        set_at=datetime.utcnow(),
        set_by_user_id="bkhoshbin",
    )

    assert pick_default.plugin_oid == topaz_oid
    assert denoise_default.plugin_oid == topaz_oid
    # Two rows; same plugin; different category PKs.
    assert pick_default.category != denoise_default.category


# ---------------------------------------------------------------------------
# Constructor smoke
# ---------------------------------------------------------------------------


def test_plugin_can_be_instantiated_with_install_payload():
    """Sanity: the install pipeline's typical kwargs round-trip."""
    p = Plugin(
        oid=uuid.uuid4(),
        name="CTF Plugin",
        manifest_plugin_id="ctf",
        version="1.0.2",
        author="Magellon Team",
        category="CTF",
        backend_id="ctffind4",
        schema_version="1",
        install_method="docker",
        install_dir="/opt/magellon/plugins/ctf",
        image_ref="magellon/ctf:1.0.2",
        archive_id="01999999-0000-7000-8000-000000000001",
        manifest_json={"plugin_id": "ctf", "version": "1.0.2"},
        installed_date=datetime.utcnow(),
        created_date=datetime.utcnow(),
    )
    assert p.manifest_plugin_id == "ctf"
    assert p.category == "CTF"
    assert p.backend_id == "ctffind4"
    assert p.install_method == "docker"
