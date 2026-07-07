"""Generic broker-plugin HTTP router.

Endpoints:
    GET  /plugins/                          - list live broker plugins
    GET  /plugins/capabilities              - categories, backends, schemas
    GET  /plugins/{plugin_id}/manifest       - announced capability manifest
    GET  /plugins/{plugin_id}/info           - plugin metadata
    GET  /plugins/{plugin_id}/health         - liveness probe
    GET  /plugins/{plugin_id}/schema/input   - input JSON schema
    GET  /plugins/{plugin_id}/schema/output  - output JSON schema
    POST /plugins/{plugin_id}/jobs           - submit one async job
    POST /plugins/{plugin_id}/jobs/batch     - fan out over N inputs
    GET  /plugins/jobs                       - list jobs
    GET  /plugins/jobs/{job_id}              - job detail

Plugin-specific sync/preview/retune routes are broker capabilities reached
through the dispatch controller. This controller covers the uniform
discovery, state, install, and async-job surfaces.

Route handlers live in :mod:`plugins.controller_registry` (discovery +
operator state), :mod:`plugins.controller_jobs` (async jobs), and
:mod:`plugins.controller_lifecycle` (install / catalog / installed);
this module assembles them into the single ``plugins_router`` and
re-exports the shared helpers so existing import sites keep working.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from dependencies.auth import get_current_user_id

from plugins.controller_jobs import jobs_router
from plugins.controller_lifecycle import lifecycle_router
from plugins.controller_registry import registry_router

# Policy: the whole plugin surface (registry reads, install/lifecycle,
# job submission) requires an authenticated user. Role escalation for
# install/uninstall is a future policy decision; today the bar matches
# the rest of the authenticated API.
plugins_router = APIRouter(dependencies=[Depends(get_current_user_id)])

plugins_router.include_router(registry_router)
plugins_router.include_router(jobs_router)
plugins_router.include_router(lifecycle_router)


# ---------------------------------------------------------------------------
# Back-compat re-exports
# ---------------------------------------------------------------------------
#
# Callers historically imported the wire models and (private) helpers
# straight from ``plugins.controller`` — e.g.
# ``controllers.particle_export_pipeline_controller`` and several test
# modules. Keep those import paths stable; new code should import from
# the service modules directly.
from plugins.dispatch_service import (  # noqa: F401,E402
    _BROKER_ENVELOPE_SOURCE,
    _build_task_dto,
    _publish_to_bus,
    _resolve_dispatch_target,
    _resolve_live_plugin_version,
    _submit_broker_batch,
    _submit_broker_job,
    _try_dispatch_cache_hit,
)
from plugins.dispatch_validation import (  # noqa: F401,E402
    _ARTIFACT_TAG_VOCAB,
    _derive_subject,
    _reject_if_subject_missing,
    _reject_if_subject_tag_mismatch,
    _validate_broker_input,
)
from plugins.install_service import (  # noqa: F401,E402
    _enforce_sdk_compat,
    _ensure_docker,
    _install_from_manifest,
    _parse_archive_bytes,
)
from plugins.registry_service import (  # noqa: F401,E402
    _MIN_DT,
    _category_contract_by_name,
    _category_for_plugin,
    _category_for_plugin_from_db,
    _live_entry,
    _live_schema_for_plugin,
    _normalize_category_key,
    _strip_category_prefix,
)
from plugins.schemas import (  # noqa: F401,E402
    BatchSubmitRequest,
    JobSubmitRequest,
    PluginSummary,
)

# The two lookup helpers below are shims rather than plain re-exports:
# existing tests (tests/test_find_broker_plugin_lenient.py,
# tests/test_schema_endpoint_db_fallback.py) patch
# ``plugins.controller.get_liveness_registry`` to steer them, so they
# must read the getter from THIS module's namespace at call time.
from typing import Optional  # noqa: E402

from core.plugin_liveness_registry import (  # noqa: E402
    get_registry as get_liveness_registry,
)
from magellon_sdk.categories.contract import CategoryContract  # noqa: E402

from plugins import registry_service as _registry_service  # noqa: E402


def _find_broker_plugin(plugin_id: str) -> Optional[CategoryContract]:
    """Back-compat shim — see :func:`plugins.registry_service._find_broker_plugin`."""
    return _registry_service._find_broker_plugin(
        plugin_id, registry=get_liveness_registry(),
    )


def _category_contract_for_plugin(plugin_id: str) -> Optional[CategoryContract]:
    """Back-compat shim — see
    :func:`plugins.registry_service._category_contract_for_plugin`."""
    return _registry_service._category_contract_for_plugin(
        plugin_id, registry=get_liveness_registry(),
    )


# Back-compat alias — the pre-2026-05 helper was named
# ``_category_for_live_plugin`` (live-registry only); see the note in
# plugins/registry_service.py.
_category_for_live_plugin = _category_contract_for_plugin
