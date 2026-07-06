"""Fail when generated/runtime-only files or secrets are tracked by git."""
from __future__ import annotations

import fnmatch
import subprocess
import sys
from pathlib import PurePosixPath


FORBIDDEN_PATTERNS = (
    "*.pyc",
    "*.pyo",
    "*.log",
    ".env",
    "*/.env",
    "*/__pycache__/*",
    "*/node_modules/*",
    "*/venv/*",
    "*/.venv/*",
    "*/dist/*",
    "*/build/*",
    "*/.pytest_cache/*",
    "*/.ruff_cache/*",
    "*/playwright-report/*",
    "*/test-results/*",
    # Personal scratch notes have leaked credentials before; keep them
    # out of the repository entirely.
    "*/MyNotes.md",
    "MyNotes.md",
    "*/messages.md",
)

# High-signal secret patterns (git grep -E). Never allowlisted.
SECRET_PATTERNS = (
    r"-----BEGIN (RSA|EC|DSA|OPENSSH|PGP) PRIVATE KEY-----",
    r"AKIA[0-9A-Z]{16}",
)

# The historical dev-stack default password. It is frozen into the dev
# infrastructure (DB dump seeds, compose files, dev settings) and is
# treated as public knowledge for local stacks — but it may never appear
# in a NEW location. This list is a ratchet: entries may be removed as
# files are cleaned up, never added. Production configs must not use it.
KNOWN_DEV_PASSWORD = "behd1d2"
KNOWN_DEV_PASSWORD_ALLOWLIST = frozenset({
    ".github/workflows/e2e-tests.yml",
    "CoreService/database/magellon01db.sql",
    "CoreService/sandbox/aws/motioncor_aws_pipeline.py",
    "CoreService/sandbox/aws/record_tasks.py",
    "CoreService/sandbox/aws/replay_plugin_stack.py",
    "CoreService/sandbox/aws/test-5-gpu-node-e2e/02-wait-ready.sh",
    "CoreService/sandbox/aws/test-5-gpu-node-e2e/compose/docker-compose.yml",
    "CoreService/sandbox/aws/test-5-gpu-node-e2e/compose/settings_prod.yml",
    "CoreService/scripts/ctf_smoke_publish.py",
    "CoreService/scripts/dispatch_ctf_test.py",
    "CoreService/scripts/dispatch_motioncor_test.py",
    "CoreService/scripts/migrate_dlq_topology.py",
    "CoreService/scripts/motioncor_smoke_publish.py",
    "CoreService/scripts/redispatch_motioncor_job.py",
    "CoreService/tests/integration/conftest.py",
    "CoreService/tests/integration/test_e2e_seam.py",
    "CoreService/tests/integration/test_fft_full_stack_e2e.py",
    "CoreService/tests/test_cancellation_service.py",
    "CoreService/tests/test_e2e_dispatch_helper.py",
    "Docker/services/mysql/init/magellon01db.sql",
    "infrastructure/Deployment/Readme.md",
    "infrastructure/Deployment/libs/config.py",
    "infrastructure/Deployment/libs/models.py",
    "infrastructure/Deployment/libs/services.py",
    "infrastructure/Deployment/magellon_config.json",
    "infrastructure/Deployment/playbooks/inventory.ini",
    "infrastructure/Deployment/playbooks/mysql.yml",
    "infrastructure/Deployment/playbooks/mysql0.yml",
    "infrastructure/Deployment/playbooks/postgresql.yml",
    "infrastructure/Deployment/screens/mysql_screen.py",
    "magellon-react-app/tests/e2e/helpers/credentials.ts",
    "magellon-sdk/tests/test_e2e_rabbitmq.py",
    "magellon-sdk/tests/test_transport_rabbitmq_integration.py",
    "plugins/magellon_boxnet_plugin/configs/settings_dev.yml",
    "plugins/magellon_can_classifier_plugin/configs/settings_dev.yml",
    "plugins/magellon_ctf_plugin/configs/settings_dev.yml",
    "plugins/magellon_ctf_plugin/configs/settings_docker_test.yml",
    "plugins/magellon_ctf_plugin/configs/settings_host.yml",
    "plugins/magellon_ctf_plugin/support/docker-compose.yml",
    "plugins/magellon_ctf_plugin/tests/README.md",
    "plugins/magellon_ctf_plugin/tests/smoke_test_docker.py",
    "plugins/magellon_fft_plugin/configs/settings_dev.yml",
    "plugins/magellon_motioncor_plugin/configs/settings_dev.yml",
    "plugins/magellon_motioncor_plugin/configs/settings_docker_test.yml",
    "plugins/magellon_motioncor_plugin/support/docker-compose.yml",
    "plugins/magellon_motioncor_plugin/tests/README.md",
    "plugins/magellon_motioncor_plugin/tests/smoke_test_docker.py",
    "plugins/magellon_ptolemy_plugin/configs/settings_dev.yml",
    "plugins/magellon_sam2_plugin/configs/settings_dev.yml",
    "plugins/magellon_stack_maker_plugin/configs/settings_dev.yml",
    "plugins/magellon_template_picker_plugin/configs/settings_dev.yml",
    "plugins/magellon_topaz_plugin/configs/settings_dev.yml",
})


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def _is_forbidden(path: str) -> bool:
    normalized = PurePosixPath(path).as_posix()
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in FORBIDDEN_PATTERNS)


def _grep_tracked(pattern: str, *, fixed: bool = False) -> list[str]:
    """Paths of tracked files whose content matches ``pattern``."""
    cmd = ["git", "grep", "-l", "-I"]
    cmd.append("-F" if fixed else "-E")
    cmd += ["-e", pattern, "--", "."]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git grep failed: {result.stderr}")
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def _secret_offenders() -> list[str]:
    offenders: list[str] = []
    for pattern in SECRET_PATTERNS:
        offenders += [f"{path}  (matches {pattern!r})" for path in _grep_tracked(pattern)]
    for path in _grep_tracked(KNOWN_DEV_PASSWORD, fixed=True):
        if path == "scripts/check_repo_hygiene.py":
            continue
        if path not in KNOWN_DEV_PASSWORD_ALLOWLIST:
            offenders.append(f"{path}  (known dev password outside the frozen allowlist)")
    return offenders


def main() -> int:
    offenders = [path for path in _tracked_files() if _is_forbidden(path)]
    if offenders:
        print("Generated/runtime-only files are tracked by git:", file=sys.stderr)
        for path in offenders:
            print(f"  {path}", file=sys.stderr)
        return 1
    secret_hits = _secret_offenders()
    if secret_hits:
        print("Potential secrets in tracked files:", file=sys.stderr)
        for hit in secret_hits:
            print(f"  {hit}", file=sys.stderr)
        return 1
    print("Repository hygiene check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
