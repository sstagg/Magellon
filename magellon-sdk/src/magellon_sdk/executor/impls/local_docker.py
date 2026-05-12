"""Run a plugin invocation inside a local Docker container.

Shells out to the ``docker`` CLI rather than depending on ``docker-py`` so
this stays a zero-cost addition for plugins / hosts that don't need it.

Lifecycle: ``submit`` runs ``docker run -d --name <name>``; ``await_result``
runs ``docker wait`` (blocks until the container exits, prints exit code);
on non-zero, ``docker logs`` is captured and surfaced via
:class:`ExecutionFailed`. The container is removed on every terminal
path (``--rm`` is intentionally NOT used so logs survive long enough to
be captured).

Configuration via :attr:`ExecutorSpec.config`:

* ``image`` — image reference (required).
* ``command`` — optional argv override (``CMD``-style); placeholders
  ``{payload}`` / ``{result}`` resolve to the *in-container* paths under
  ``/work`` (which is where ``run_dir`` is bind-mounted).
* ``gpus`` — value passed to ``--gpus`` (e.g. ``"all"`` or ``"device=0"``).
* ``mounts`` — list of ``"hostpath:containerpath"`` extras.
* ``env`` — extra env vars passed via ``-e``.
* ``network`` — value for ``--network``.
"""
from __future__ import annotations

import shlex
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from magellon_sdk.executor.base import ExecutionHandle, ExecutorSpec
from magellon_sdk.executor.impls._common import (
    ExecutionFailed,
    ExecutionNotFound,
    ProcessRunner,
    default_run_cmd,
    read_result,
    substitute_placeholders,
    tail,
    write_payload,
)
from magellon_sdk.progress import ProgressReporter


CONTAINER_WORK_DIR = "/work"


class LocalDockerExecutor:
    """Carry a plugin invocation into a ``docker run`` container."""

    kind = "localdocker"

    def __init__(
        self,
        work_dir: Optional[Path] = None,
        *,
        docker_cli: str = "docker",
        process_runner: ProcessRunner = default_run_cmd,
    ) -> None:
        self.work_dir = Path(work_dir) if work_dir else Path(tempfile.gettempdir()) / "magellon-localdocker"
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.docker_cli = docker_cli
        self._run = process_runner
        self._known: Dict[str, ExecutionHandle] = {}

    async def submit(
        self,
        *,
        plugin_id: str,
        input_payload: Dict[str, Any],
        spec: ExecutorSpec,
        reporter: ProgressReporter,
    ) -> ExecutionHandle:
        image = spec.config.get("image")
        if not image:
            raise ValueError("localdocker executor requires spec.config['image']")

        execution_id = uuid.uuid4().hex
        run_dir = self.work_dir / execution_id
        write_payload(run_dir, input_payload)
        result_path = run_dir / "result.json"
        container_name = f"magellon-{execution_id[:12]}"

        argv = [self.docker_cli, "run", "-d", "--name", container_name]

        if spec.config.get("gpus"):
            argv += ["--gpus", str(spec.config["gpus"])]
        if spec.config.get("network"):
            argv += ["--network", str(spec.config["network"])]

        argv += ["-v", f"{run_dir}:{CONTAINER_WORK_DIR}"]
        for mount in spec.config.get("mounts") or []:
            argv += ["-v", str(mount)]

        for k, v in (spec.config.get("env") or {}).items():
            argv += ["-e", f"{k}={v}"]

        argv.append(image)

        if spec.config.get("command"):
            cmd_in_container = substitute_placeholders(
                list(spec.config["command"]),
                payload=f"{CONTAINER_WORK_DIR}/input.json",
                result=f"{CONTAINER_WORK_DIR}/result.json",
                run_dir=CONTAINER_WORK_DIR,
            )
            argv += cmd_in_container

        rc, stdout, stderr = await self._run(argv)
        if rc != 0:
            raise ExecutionFailed(
                f"docker-run-{rc}",
                tail(stderr.decode("utf-8", "replace")),
            )
        container_id = stdout.decode("utf-8", "replace").strip()

        reporter.report(0, f"docker container {container_name}")

        handle = ExecutionHandle(
            executor_kind=self.kind,
            execution_id=execution_id,
            container_id=container_id,
            container_name=container_name,
            result_path=str(result_path),
            run_dir=str(run_dir),
        )
        self._known[execution_id] = handle
        return handle

    async def await_result(
        self,
        handle: ExecutionHandle,
        *,
        timeout_s: Optional[float] = None,
    ) -> Dict[str, Any]:
        container_id = getattr(handle, "container_id", None)
        if not container_id:
            raise ExecutionNotFound(handle.execution_id)

        # `docker wait` blocks until the container exits and prints the exit
        # code on stdout. Honour the caller's timeout via wait_for.
        import asyncio  # local to keep top-level imports clean

        try:
            rc, stdout, stderr = await asyncio.wait_for(
                self._run([self.docker_cli, "wait", container_id]),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError:
            raise

        if rc != 0:
            # `docker wait` itself failed — container gone, daemon down, etc.
            raise ExecutionFailed(
                f"docker-wait-{rc}",
                tail(stderr.decode("utf-8", "replace")),
            )

        try:
            container_exit = int(stdout.decode("utf-8", "replace").strip().splitlines()[-1])
        except (ValueError, IndexError) as exc:
            raise ExecutionFailed("docker-wait-parse", repr(exc)) from exc

        if container_exit != 0:
            logs = await self._fetch_logs(container_id)
            await self._remove(container_id)
            raise ExecutionFailed(f"container-exit-{container_exit}", tail(logs))

        result = read_result(Path(handle.result_path))
        await self._remove(container_id)
        return result

    async def cancel(self, handle: ExecutionHandle) -> None:
        container_id = getattr(handle, "container_id", None)
        if not container_id:
            return
        # `docker kill` is idempotent enough — already-exited containers
        # return non-zero but we don't care; the user asked for cancel and
        # the container is no longer running either way.
        await self._run([self.docker_cli, "kill", container_id])
        await self._remove(container_id)

    async def _fetch_logs(self, container_id: str) -> str:
        rc, stdout, stderr = await self._run([self.docker_cli, "logs", container_id])
        if rc != 0:
            return stderr.decode("utf-8", "replace")
        # docker logs interleaves stdout+stderr by default in two streams;
        # merge them for the failure tail.
        return (stdout + b"\n" + stderr).decode("utf-8", "replace")

    async def _remove(self, container_id: str) -> None:
        await self._run([self.docker_cli, "rm", "-f", container_id])


def render_docker_argv(spec_config: Dict[str, Any], *, run_dir: Path, container_name: str, docker_cli: str = "docker") -> str:
    """Helper for debugging: render the docker argv as a shell string."""
    image = spec_config["image"]
    argv = [docker_cli, "run", "-d", "--name", container_name, "-v", f"{run_dir}:{CONTAINER_WORK_DIR}"]
    if spec_config.get("gpus"):
        argv += ["--gpus", str(spec_config["gpus"])]
    argv.append(image)
    if spec_config.get("command"):
        argv += list(spec_config["command"])
    return shlex.join(argv)


__all__ = ["LocalDockerExecutor", "render_docker_argv"]
