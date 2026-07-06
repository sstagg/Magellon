"""Route-table auth gate.

Walks every HTTP route on the app and asserts it either carries an
authentication/authorization dependency or is on the explicit public
allowlist below. This turns "we meant to secure everything" into a CI
gate: adding a new unauthenticated route fails this test until the
route is either given an auth dependency or deliberately allowlisted
here with a justification.
"""
from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

import main

# Dependencies defined in these modules count as authentication or
# authorization. require_role/require_permission return closures whose
# __module__ is dependencies.permissions, so they match too.
AUTH_DEPENDENCY_MODULES = (
    "dependencies.auth",
    "dependencies.permissions",
)

# Callables that gate access without living in dependencies/ (docs
# basic-auth checker lives in main).
AUTH_DEPENDENCY_NAMES = {
    "verify_docs_credentials",
}

# Deliberately public routes. Every entry needs a reason.
PUBLIC_EXACT = {
    # Liveness/readiness must be probeable by orchestrators.
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
    # Legacy liveness path still used by older probes/scripts.
    ("GET", "/health"),
    # Login is how you obtain a token; logout without a token is a no-op.
    ("POST", "/auth/login"),
    ("POST", "/auth/logout"),
    # Security bootstrap: self-gating via security_setup_settings
    # (ENABLED flag + setup token + completion marker file).
    ("POST", "/auth/setup"),
    # Login-equivalent credential check used by the older UI flow.
    ("POST", "/db/security/users/authenticate"),
    # Deliberately public lost-admin-password recovery aid: hashes a
    # caller-supplied password for manual DB insertion; reads nothing.
    ("POST", "/db/security/users/generate-password-hash"),
    # Static landing pages, no data access.
    ("GET", "/"),
    ("GET", "/html"),
    ("GET", "/en/{rest_of_path:path}"),
    # Prometheus scrape endpoint; protect at network level if needed.
    ("GET", "/metrics"),
}

# Public prefixes (path startswith). Keep short and justified.
PUBLIC_PREFIXES: tuple[str, ...] = ()


def _dependency_calls(dependant):
    """Flatten the dependency tree of a route into its callables."""
    for dep in dependant.dependencies:
        if dep.call is not None:
            yield dep.call
        yield from _dependency_calls(dep)


def _has_auth_dependency(route: APIRoute) -> bool:
    for call in _dependency_calls(route.dependant):
        module = getattr(call, "__module__", "") or ""
        name = getattr(call, "__name__", "") or ""
        if module.startswith(AUTH_DEPENDENCY_MODULES):
            return True
        if name in AUTH_DEPENDENCY_NAMES:
            return True
    return False


def _is_public(method: str, path: str) -> bool:
    if (method, path) in PUBLIC_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES)


def _iter_http_routes():
    for route in main.app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(route.methods or ()):
            if method in ("HEAD", "OPTIONS"):
                continue
            yield method, route.path, route


def test_every_route_is_authenticated_or_allowlisted():
    offenders = []
    for method, path, route in _iter_http_routes():
        if _is_public(method, path):
            continue
        if not _has_auth_dependency(route):
            offenders.append(f"{method} {path}  ({route.endpoint.__module__})")
    assert not offenders, (
        "Routes without an auth dependency that are not on the public "
        "allowlist:\n  " + "\n  ".join(sorted(offenders))
    )


def test_public_allowlist_matches_real_routes():
    """Allowlist hygiene: every allowlisted route must still exist, so
    stale entries can't silently keep a future route public."""
    existing = {(m, p) for m, p, _ in _iter_http_routes()}
    stale = PUBLIC_EXACT - existing
    assert not stale, f"Public allowlist entries no longer in the app: {sorted(stale)}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
