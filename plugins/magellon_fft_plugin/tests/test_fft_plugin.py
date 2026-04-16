"""Unit tests for the broker-native ``FftPlugin`` and its runner glue.

These tests stay off the broker — they pin the contract pieces that the
runner harness expects and the result-factory shape downstream code
relies on. The full RMQ/NATS path is exercised by
``tests/integration/test_fft_messaging_e2e.py``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest

# Make the FFT plugin importable as ``core.*`` / ``service.*`` —
# matches conftest pattern used by the integration tests.
_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))


# ---------------------------------------------------------------------------
# FftPlugin contract
# ---------------------------------------------------------------------------


def test_input_and_output_schema_match_fft_category_contract():
    """FftPlugin must satisfy the FFT CategoryContract — same input and
    output models. If this drifts, the dispatcher and the plugin can't
    speak the same language."""
    from magellon_sdk.categories.contract import FFT
    from plugin.plugin import FftPlugin

    assert FftPlugin.input_schema() is FFT.input_model
    assert FftPlugin.output_schema() is FFT.output_model


def test_get_info_matches_manifest_provenance():
    """plugin_id/plugin_version stamped on results come from get_info().
    Pin the values so the audit trail (P4) stays predictable."""
    from plugin.plugin import FftPlugin

    info = FftPlugin().get_info()
    assert info.name == "FFT Plugin"
    assert info.version == "1.0.0"


def test_manifest_advertises_progress_and_rmq_default():
    """Capability + transport defaults — these flow into the announce
    payload, so a regression here would silently misregister the plugin."""
    from magellon_sdk.models.manifest import Capability, Transport
    from plugin.plugin import FftPlugin

    manifest = FftPlugin().manifest()
    assert Capability.PROGRESS_REPORTING in manifest.capabilities
    assert manifest.default_transport == Transport.RMQ


# ---------------------------------------------------------------------------
# execute() — pure compute path, step events disabled
# ---------------------------------------------------------------------------


def test_execute_returns_fft_output_with_paths(monkeypatch, tmp_path):
    """Sync execute() runs compute_file_fft and returns FftOutput with
    the resolved paths. Step events stay off (no active task) so the
    test doesn't need a broker."""
    from magellon_sdk.categories.outputs import FftOutput
    from magellon_sdk.models.tasks import FftTaskData
    from plugin import plugin as plugin_mod

    captured = {}

    def _fake_fft(image_path, abs_out_file_name, height=1024):
        captured["image_path"] = image_path
        captured["out"] = abs_out_file_name
        return abs_out_file_name

    monkeypatch.setattr(plugin_mod, "compute_file_fft", _fake_fft)

    img = tmp_path / "img.mrc"
    target = tmp_path / "img_FFT.png"
    out = plugin_mod.FftPlugin().execute(
        FftTaskData(image_path=str(img), target_path=str(target))
    )

    assert isinstance(out, FftOutput)
    assert out.output_path == str(target)
    assert out.source_image_path == str(img)
    assert captured == {"image_path": str(img), "out": str(target)}


def test_execute_resolves_output_path_when_target_omitted(monkeypatch, tmp_path):
    """No target_path → derive ``<stem>_FFT.png`` next to the input. The
    HTTP path's _resolve_output_path has the same rule; both must agree."""
    from magellon_sdk.models.tasks import FftTaskData
    from plugin import plugin as plugin_mod

    monkeypatch.setattr(
        plugin_mod, "compute_file_fft",
        lambda image_path, abs_out_file_name, height=1024: abs_out_file_name,
    )

    img = tmp_path / "sample.mrc"
    out = plugin_mod.FftPlugin().execute(FftTaskData(image_path=str(img)))
    assert out.output_path == str(tmp_path / "sample_FFT.png")


def test_execute_raises_when_neither_path_supplied():
    """A task with neither image_path nor target_path can't compute —
    raise so the runner classifies into DLQ via P2's exception taxonomy
    rather than silently producing an empty FftOutput."""
    from magellon_sdk.models.tasks import FftTaskData
    from plugin.plugin import FftPlugin

    with pytest.raises(ValueError, match="image_path or target_path"):
        FftPlugin().execute(FftTaskData())


# ---------------------------------------------------------------------------
# build_fft_result — wire shape
# ---------------------------------------------------------------------------


def test_build_fft_result_carries_envelope_identifiers():
    """The result must echo job_id/task_id from the envelope so
    JobEventWriter can correlate it back to the originating task."""
    from magellon_sdk.categories.outputs import FftOutput
    from magellon_sdk.models import TaskDto
    from plugin.plugin import build_fft_result

    job_id = uuid4()
    task_id = uuid4()
    task = TaskDto(id=task_id, job_id=job_id, data={})
    output = FftOutput(output_path="/tmp/out.png", source_image_path="/tmp/in.mrc")

    result = build_fft_result(task, output)

    assert result.job_id == job_id
    assert result.task_id == task_id
    assert result.message == "FFT successfully executed"
    assert result.code == 200
    assert result.image_path == "/tmp/in.mrc"
    assert len(result.output_files) == 1
    assert result.output_files[0].path == "/tmp/out.png"
    assert result.output_files[0].name == "out.png"
    assert result.output_files[0].required is True
    assert result.output_data["output_path"] == "/tmp/out.png"


def test_build_fft_result_merges_output_extras_into_output_data():
    """Plugin-specific extras on FftOutput must be preserved on the
    result. Generic consumers ignore them; specialized ones can read."""
    from magellon_sdk.categories.outputs import FftOutput
    from magellon_sdk.models import TaskDto
    from plugin.plugin import build_fft_result

    task = TaskDto(id=uuid4(), job_id=uuid4(), data={})
    output = FftOutput(
        output_path="/tmp/out.png",
        extras={"radial_profile_path": "/tmp/profile.csv"},
    )

    result = build_fft_result(task, output)
    assert result.output_data["radial_profile_path"] == "/tmp/profile.csv"
    assert result.output_data["output_path"] == "/tmp/out.png"


# ---------------------------------------------------------------------------
# FftBrokerRunner._process — TaskDto exposed via ContextVar
# ---------------------------------------------------------------------------


def test_runner_exposes_active_task_during_plugin_run(monkeypatch, tmp_path):
    """The runner must populate get_active_task() before plugin.run() so
    execute() can recover job_id/task_id for step-event emission. After
    _process returns the var is reset to its prior value."""
    from magellon_sdk.models import TaskDto
    from plugin import plugin as plugin_mod
    from plugin.plugin import (
        FftBrokerRunner,
        FftPlugin,
        build_fft_result,
        get_active_task,
    )

    monkeypatch.setattr(
        plugin_mod, "compute_file_fft",
        lambda image_path, abs_out_file_name, height=1024: abs_out_file_name,
    )

    seen = {}

    class CapturingPlugin(FftPlugin):
        def execute(self, input_data, *, reporter=None):
            seen["task"] = get_active_task()
            return super().execute(input_data, reporter=reporter or _null_reporter())

    runner = FftBrokerRunner(
        plugin=CapturingPlugin(),
        settings=_FakeRmqSettings(),
        in_queue="fft_tasks_queue",
        out_queue="fft_out_tasks_queue",
        result_factory=build_fft_result,
        contract=None,           # disable discovery/config — no broker here
        enable_discovery=False,
        enable_config=False,
    )

    job_id = uuid4()
    task_id = uuid4()
    task = TaskDto(
        id=task_id,
        job_id=job_id,
        data={"image_path": str(tmp_path / "x.mrc"), "target_path": str(tmp_path / "x.png")},
    )

    out_bytes = runner._process(task.model_dump_json().encode("utf-8"))

    # ContextVar exposed to plugin during the call
    assert seen["task"].id == task_id
    assert seen["task"].job_id == job_id
    # …and reset afterwards so a stray call wouldn't see stale state.
    assert get_active_task() is None

    # The bytes the runner publishes must be the JSON-encoded TaskResultDto.
    import json
    payload = json.loads(out_bytes.decode("utf-8"))
    assert payload["task_id"] == str(task_id)
    assert payload["job_id"] == str(job_id)
    # Provenance auto-stamped (P4) from get_info().
    assert payload["plugin_id"] == "FFT Plugin"
    assert payload["plugin_version"] == "1.0.0"


def test_handle_task_exposes_active_task_during_bus_driven_run(monkeypatch, tmp_path):
    """MB4.2: the production path is bus-driven — _handle_task must
    set the ContextVar just like _process does, so step-event
    emission inside execute() still sees the active TaskDto."""
    from magellon_sdk.bus import DefaultMessageBus
    from magellon_sdk.bus.binders.mock import MockBinder
    from magellon_sdk.envelope import Envelope
    from magellon_sdk.models import TaskDto
    from plugin import plugin as plugin_mod
    from plugin.plugin import (
        FftBrokerRunner,
        FftPlugin,
        build_fft_result,
        get_active_task,
    )

    monkeypatch.setattr(
        plugin_mod, "compute_file_fft",
        lambda image_path, abs_out_file_name, height=1024: abs_out_file_name,
    )

    seen = {}

    class CapturingPlugin(FftPlugin):
        def execute(self, input_data, *, reporter=None):
            seen["task"] = get_active_task()
            return super().execute(input_data, reporter=reporter or _null_reporter())

    bus = DefaultMessageBus(MockBinder())
    bus.start()
    try:
        runner = FftBrokerRunner(
            plugin=CapturingPlugin(),
            settings=_FakeRmqSettings(),
            in_queue="fft_tasks_queue",
            out_queue="fft_out_tasks_queue",
            result_factory=build_fft_result,
            contract=None,
            enable_discovery=False,
            enable_config=False,
            bus=bus,
        )

        job_id = uuid4()
        task_id = uuid4()
        task = TaskDto(
            id=task_id,
            job_id=job_id,
            data={"image_path": str(tmp_path / "x.mrc"), "target_path": str(tmp_path / "x.png")},
        )
        envelope = Envelope.wrap(
            source="test", type="magellon.task.dispatch",
            subject="fft_tasks_queue", data=task,
        )

        runner._handle_task(envelope)

        assert seen["task"].id == task_id
        assert seen["task"].job_id == job_id
        assert get_active_task() is None  # reset after return
    finally:
        bus.close()


# ---------------------------------------------------------------------------
# Step events — emitted via the daemon loop when active task + publisher
# are present
# ---------------------------------------------------------------------------


def test_execute_emits_started_progress_completed_when_publisher_present(
    monkeypatch, tmp_path
):
    """Sync execute() bridges to the async step-event publisher via the
    daemon loop. Pin the order and the keyword shape."""
    from magellon_sdk.models import TaskDto
    from plugin import plugin as plugin_mod

    calls = []

    class _RecPub:
        async def publish(self, subject, envelope):
            calls.append((envelope.type, envelope.data))

    async def _get_publisher():
        # Wrap the recording pub in StepEventPublisher to keep the
        # plugin's BoundStepReporter wiring intact.
        from magellon_sdk.events import StepEventPublisher
        return StepEventPublisher(_RecPub(), plugin_name="fft")

    monkeypatch.setattr(plugin_mod, "get_publisher", _get_publisher)
    monkeypatch.setattr(
        plugin_mod, "compute_file_fft",
        lambda image_path, abs_out_file_name, height=1024: abs_out_file_name,
    )

    job_id = uuid4()
    task_id = uuid4()
    task = TaskDto(id=task_id, job_id=job_id, data={})
    token = plugin_mod._active_task.set(task)
    try:
        from magellon_sdk.models.tasks import FftTaskData
        plugin_mod.FftPlugin().execute(
            FftTaskData(
                image_path=str(tmp_path / "img.mrc"),
                target_path=str(tmp_path / "img_FFT.png"),
            )
        )
    finally:
        plugin_mod._active_task.reset(token)

    types = [c[0] for c in calls]
    assert types == [
        "magellon.step.started",
        "magellon.step.progress",
        "magellon.step.progress",
        "magellon.step.completed",
    ]
    for _, data in calls:
        assert data["job_id"] == str(job_id)
        assert data["task_id"] == str(task_id)
        assert data["step"] == "fft"


def test_execute_emits_failed_on_compute_error(monkeypatch, tmp_path):
    """A crash inside compute_file_fft must produce a failed envelope
    *and* re-raise so the runner can NACK + classify per P2."""
    from magellon_sdk.models import TaskDto
    from plugin import plugin as plugin_mod

    calls = []

    class _RecPub:
        async def publish(self, subject, envelope):
            calls.append((envelope.type, envelope.data))

    async def _get_publisher():
        from magellon_sdk.events import StepEventPublisher
        return StepEventPublisher(_RecPub(), plugin_name="fft")

    def _boom(image_path, abs_out_file_name, height=1024):
        raise RuntimeError("fft crashed")

    monkeypatch.setattr(plugin_mod, "get_publisher", _get_publisher)
    monkeypatch.setattr(plugin_mod, "compute_file_fft", _boom)

    task = TaskDto(id=uuid4(), job_id=uuid4(), data={})
    token = plugin_mod._active_task.set(task)
    try:
        from magellon_sdk.models.tasks import FftTaskData
        with pytest.raises(RuntimeError, match="fft crashed"):
            plugin_mod.FftPlugin().execute(
                FftTaskData(
                    image_path=str(tmp_path / "img.mrc"),
                    target_path=str(tmp_path / "img_FFT.png"),
                )
            )
    finally:
        plugin_mod._active_task.reset(token)

    types = [c[0] for c in calls]
    # Expect: started, progress(loading), failed — second progress is
    # skipped because the crash happens between the two ticks.
    assert types == [
        "magellon.step.started",
        "magellon.step.progress",
        "magellon.step.failed",
    ]
    assert calls[-1][1]["error"] == "fft crashed"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


class _FakeRmqSettings:
    HOST_NAME = "localhost"
    PORT = 5672
    USER_NAME = "guest"
    PASSWORD = "guest"
    VIRTUAL_HOST = "/"


def _null_reporter():
    from magellon_sdk.progress import NullReporter
    return NullReporter()
