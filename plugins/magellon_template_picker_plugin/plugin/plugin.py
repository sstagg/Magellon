"""External (broker-resident) template-picker plugin.

Phase 6 (2026-05-03). Forks the FFT blueprint to ship a
broker-resident template picker for the PARTICLE_PICKING category
(code 3, backend_id ``template-picker``).

**Principle 4 caveat.** The in-process picker at
``CoreService/plugins/pp/template_picker/`` already serves
PARTICLE_PICKING in production. This external version pays its way
when:
  * a deployment wants to scale the picker independently of
    CoreService (separate container, separate replicas);
  * a deployment wants the picker on a different host (e.g. a CPU
    box near the data plane while CoreService runs on the API host).

If neither driver applies, prefer the in-process path. Both backends
register against the same category — the dispatcher's backend axis
(X.1, 2026-04-27) routes to the named one via
``TaskMessage.target_backend``.
"""
from __future__ import annotations

import logging
import os
from typing import Type

from magellon_sdk.base import PluginBase
from magellon_sdk.categories.outputs import Particle, ParticlePickingOutput
from magellon_sdk.models import OutputFile, PluginInfo, TaskMessage, TaskResultMessage
from magellon_sdk.models.manifest import (
    Capability,
    IsolationLevel,
    ResourceHints,
    Transport,
)
from magellon_sdk.models.tasks import CryoEmImageInput  # legacy, kept for typing of preview() input
from magellon_sdk.progress import NullReporter, ProgressReporter
from magellon_sdk.runner import emit_step, make_step_reporter

from plugin.compute import _resolve_template_paths, run_template_pick
from plugin.events import STEP_NAME, get_publisher
from plugin.models import TemplatePickerInput

logger = logging.getLogger(__name__)


class TemplatePickerPlugin(PluginBase[TemplatePickerInput, ParticlePickingOutput]):
    """FFT-correlation template picker.

    Inputs (via :class:`CryoEmImageInput`):

      * ``image_path`` — MRC to pick on.
      * ``engine_opts`` — required keys: ``templates`` (path / list /
        glob), ``diameter_angstrom``, ``pixel_size_angstrom``.
        Optional: ``template_pixel_size_angstrom`` (defaults to
        ``pixel_size_angstrom``), ``threshold``, ``bin``,
        ``max_peaks``, ``overlap_multiplier``,
        ``min_blob_roundness``, ``angle_ranges``,
        ``output_dir``.

    Output is a :class:`ParticlePickingOutput` with
    ``particles_json_path`` set; ``picks`` is omitted (rule 1: refs
    only on bus, no inline file content).
    """

    capabilities = [
        Capability.CPU_INTENSIVE,
        Capability.IDEMPOTENT,
        Capability.PROGRESS_REPORTING,
        # PT-4 (2026-05-04): expose sync HTTP endpoints alongside the
        # bus consumer. Plugin manager / particle-picking UI calls
        # SYNC for the "run-on-one-image" feature; PREVIEW for the
        # interactive threshold-slider loop. Same compute as bus path
        # — different transport.
        Capability.SYNC,
        Capability.PREVIEW,
    ]
    supported_transports = [
        Transport.RMQ,
        Transport.NATS,
        Transport.HTTP,
        Transport.IN_PROCESS,
    ]
    default_transport = Transport.RMQ
    isolation = IsolationLevel.CONTAINER
    resource_hints = ResourceHints(
        memory_mb=1500, cpu_cores=2, typical_duration_seconds=15.0
    )
    tags = ["template-picker", "particle-picking", "cryo-em"]

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="template-picker",
            version="0.1.0",
            developer="Behdad Khoshbin b.khoshbin@gmail.com",
            description=(
                "FFT-correlation template-matching particle picker. "
                "Mirrors the in-process pp/template_picker; deploy this "
                "external version when picker scaling is needed."
            ),
        )

    @classmethod
    def input_schema(cls) -> Type[TemplatePickerInput]:
        return TemplatePickerInput

    @classmethod
    def output_schema(cls) -> Type[ParticlePickingOutput]:
        return ParticlePickingOutput

    def execute(
        self,
        input_data: TemplatePickerInput,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> ParticlePickingOutput:
        # Typed fields straight off the model — the plugin owns its
        # input shape (PE2-UI, 2026-05-12), no more engine_opts dict
        # round-trip. ``run_template_pick`` still gets engine_opts as a
        # passthrough kwarg for any algorithm-internal knobs we haven't
        # promoted to typed fields yet.
        if not input_data.image_path:
            raise ValueError("template-picker: image_path is required")

        step = make_step_reporter(STEP_NAME, get_publisher)
        if step is not None:
            emit_step(step.started())
        try:
            template_paths = _resolve_template_paths(input_data.template_paths)
            if step is not None:
                emit_step(
                    step.progress(
                        15.0,
                        f"matching against {len(template_paths)} templates",
                    )
                )
            summary = run_template_pick(
                image_path=input_data.image_path,
                template_paths=template_paths,
                diameter_angstrom=float(input_data.diameter_angstrom),
                pixel_size_angstrom=float(input_data.image_pixel_size),
                template_pixel_size_angstrom=float(input_data.template_pixel_size),
                threshold=float(input_data.threshold),
                output_dir=input_data.output_dir,
                engine_opts=input_data.model_dump(),
            )
            if step is not None:
                emit_step(
                    step.progress(95.0, f"found {summary['num_particles']} particles")
                )
                emit_step(step.completed(output_files=[summary["particles_json_path"]]))

            return ParticlePickingOutput(
                num_particles=summary["num_particles"],
                particles_json_path=summary["particles_json_path"],
                image_shape=summary["image_shape"],
                # Per ratified rule 1 (bus carries refs + summaries
                # only): leave ``picks`` empty even for small result
                # sets. Consumers read the JSON file by path.
                picks=None,
            )
        except Exception as exc:
            if step is not None:
                emit_step(step.failed(error=str(exc)))
            raise

    # ------------------------------------------------------------------
    # PT-4: SYNC capability — sync alternative to bus dispatch.
    # Same compute as ``execute()`` minus the step-event machinery,
    # since sync calls don't ride the bus and the host is awaiting
    # the response directly.
    # ------------------------------------------------------------------

    def execute_sync(
        self, input_data: TemplatePickerInput,
    ) -> ParticlePickingOutput:
        return self.execute(input_data, reporter=NullReporter())

    # ------------------------------------------------------------------
    # PT-4: PREVIEW capability — interactive preview-and-retune flow.
    # PE2-UI (2026-05-12): preview takes the plugin's typed input
    # model, same shape as ``execute_sync``. The SDK's
    # ``make_preview_router`` validates the POST body against
    # ``cls.input_schema()``, so /preview now expects the rich
    # ``TemplatePickerInput`` JSON shape.
    # ------------------------------------------------------------------

    def preview(self, input_data: TemplatePickerInput):
        from plugin.preview import run_preview
        return run_preview(input_data)

    def retune(self, preview_id, params):
        from plugin.preview import run_retune
        return run_retune(preview_id, params)

    def discard_preview(self, preview_id) -> bool:
        from plugin.preview import discard_preview
        return discard_preview(preview_id)


def build_pick_result(
    task: TaskMessage, output: ParticlePickingOutput
) -> TaskResultMessage:
    import uuid as _uuid
    files = []
    if output.particles_json_path:
        files.append(
            OutputFile(
                name=os.path.basename(output.particles_json_path),
                path=output.particles_json_path,
                required=True,
            )
        )
    data = task.data if isinstance(task.data, dict) else {}
    image_id = None
    raw_id = data.get("image_id")
    if raw_id is not None:
        try:
            image_id = _uuid.UUID(str(raw_id))
        except (ValueError, AttributeError):
            pass
    return TaskResultMessage(
        worker_instance_id=task.worker_instance_id,
        job_id=task.job_id,
        task_id=task.id,
        image_id=image_id,
        image_path=data.get("image_path", ""),
        session_id=task.session_id,
        session_name=task.session_name,
        code=200,
        message=f"Template picker found {output.num_particles} particles",
        type=task.type,
        output_data={
            "num_particles": output.num_particles,
            "particles_json_path": output.particles_json_path,
            "image_shape": output.image_shape,
            "ipp_name": data.get("ipp_name", "Auto-pick"),
            **output.extras,
        },
        output_files=files,
    )


__all__ = [
    "TemplatePickerPlugin",
    "build_pick_result",
]
