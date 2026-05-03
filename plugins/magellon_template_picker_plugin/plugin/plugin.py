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
from magellon_sdk.models.tasks import CryoEmImageInput
from magellon_sdk.progress import NullReporter, ProgressReporter
from magellon_sdk.runner import emit_step, make_step_reporter

from plugin.compute import _resolve_template_paths, run_template_pick
from plugin.events import STEP_NAME, get_publisher

logger = logging.getLogger(__name__)


class TemplatePickerPlugin(PluginBase[CryoEmImageInput, ParticlePickingOutput]):
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
            name="Template Picker",
            version="0.1.0",
            developer="Behdad Khoshbin b.khoshbin@gmail.com",
            description=(
                "FFT-correlation template-matching particle picker. "
                "Mirrors the in-process pp/template_picker; deploy this "
                "external version when picker scaling is needed."
            ),
        )

    @classmethod
    def input_schema(cls) -> Type[CryoEmImageInput]:
        return CryoEmImageInput

    @classmethod
    def output_schema(cls) -> Type[ParticlePickingOutput]:
        return ParticlePickingOutput

    def execute(
        self,
        input_data: CryoEmImageInput,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> ParticlePickingOutput:
        opts = input_data.engine_opts or {}
        if not input_data.image_path:
            raise ValueError("template-picker: image_path is required")
        if "templates" not in opts:
            raise ValueError(
                "template-picker: engine_opts['templates'] is required "
                "(path, list of paths, or glob)"
            )
        if "diameter_angstrom" not in opts:
            raise ValueError("template-picker: engine_opts['diameter_angstrom'] is required")
        if "pixel_size_angstrom" not in opts:
            raise ValueError(
                "template-picker: engine_opts['pixel_size_angstrom'] is required"
            )

        step = make_step_reporter(STEP_NAME, get_publisher)
        if step is not None:
            emit_step(step.started())
        try:
            template_paths = _resolve_template_paths(opts["templates"])
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
                diameter_angstrom=float(opts["diameter_angstrom"]),
                pixel_size_angstrom=float(opts["pixel_size_angstrom"]),
                template_pixel_size_angstrom=(
                    float(opts["template_pixel_size_angstrom"])
                    if "template_pixel_size_angstrom" in opts
                    else None
                ),
                threshold=float(opts.get("threshold", 0.4)),
                output_dir=opts.get("output_dir"),
                engine_opts=opts,
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


def build_pick_result(
    task: TaskMessage, output: ParticlePickingOutput
) -> TaskResultMessage:
    files = []
    if output.particles_json_path:
        files.append(
            OutputFile(
                name=os.path.basename(output.particles_json_path),
                path=output.particles_json_path,
                required=True,
            )
        )
    return TaskResultMessage(
        worker_instance_id=task.worker_instance_id,
        job_id=task.job_id,
        task_id=task.id,
        session_id=task.session_id,
        session_name=task.session_name,
        code=200,
        message=f"Template picker found {output.num_particles} particles",
        type=task.type,
        output_data={
            "num_particles": output.num_particles,
            "particles_json_path": output.particles_json_path,
            "image_shape": output.image_shape,
            **output.extras,
        },
        output_files=files,
    )


__all__ = [
    "TemplatePickerPlugin",
    "build_pick_result",
]
