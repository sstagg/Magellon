"""Particle extraction (stack maker) plugin.

Phase 5 (2026-05-03). Category: PARTICLE_EXTRACTION (code 10),
backend_id: stack-maker. Subject is the source micrograph; one task
per micrograph; emits one ``particle_stack`` artifact (Phase 4
follow-up wires the artifact projection in TaskOutputProcessor).

Per ratified rule 1 (project_artifact_bus_invariants.md): the bus
carries ``mrcs_path`` / ``star_path`` refs and scalar summaries
(``particle_count``, ``apix``, ``box_size``); never the file content.
"""
from __future__ import annotations

import logging
import os
from typing import Type

from magellon_sdk.base import PluginBase
from magellon_sdk.categories.outputs import ParticleExtractionOutput
from magellon_sdk.models import (
    OutputFile,
    PluginInfo,
    TaskMessage,
    TaskResultMessage,
)
from magellon_sdk.models.manifest import (
    Capability,
    IsolationLevel,
    ResourceHints,
    Transport,
)
from magellon_sdk.models.tasks import ParticleExtractionInput
from magellon_sdk.progress import NullReporter, ProgressReporter
from magellon_sdk.runner import emit_step, make_step_reporter

from plugin.compute import extract_particles
from plugin.events import STEP_NAME, get_publisher

logger = logging.getLogger(__name__)


class StackMakerPlugin(PluginBase[ParticleExtractionInput, ParticleExtractionOutput]):
    """Box particles from a micrograph given a picker's coordinate file."""

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
        memory_mb=2000, cpu_cores=2, typical_duration_seconds=10.0
    )
    tags = ["particle-extraction", "stack-maker", "cryo-em"]

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="Stack Maker",
            version="0.1.0",
            developer="Behdad Khoshbin b.khoshbin@gmail.com",
            description=(
                "Extracts boxed particles from a micrograph given picker "
                "coordinates; emits RELION .mrcs + .star + companion .json."
            ),
        )

    @classmethod
    def input_schema(cls) -> Type[ParticleExtractionInput]:
        return ParticleExtractionInput

    @classmethod
    def output_schema(cls) -> Type[ParticleExtractionOutput]:
        return ParticleExtractionOutput

    def execute(
        self,
        input_data: ParticleExtractionInput,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> ParticleExtractionOutput:
        step = make_step_reporter(STEP_NAME, get_publisher)
        if step is not None:
            emit_step(step.started())
        try:
            opts = input_data.engine_opts or {}
            allow_partial = bool(opts.get("allow_partial", True))

            if step is not None:
                emit_step(step.progress(10.0, "loading micrograph"))

            summary = extract_particles(
                micrograph_path=input_data.micrograph_path,
                particles_path=input_data.particles_path,
                box_size=input_data.box_size,
                edge_width=input_data.edge_width,
                apix=input_data.apix,
                output_dir=input_data.output_dir,
                ctf_path=input_data.ctf_path,
                allow_partial=allow_partial,
            )

            if step is not None:
                emit_step(
                    step.progress(95.0, f"boxed {summary['particle_count']} particles")
                )
                emit_step(
                    step.completed(
                        output_files=[summary["mrcs_path"], summary["star_path"]]
                    )
                )

            return ParticleExtractionOutput(
                mrcs_path=summary["mrcs_path"],
                star_path=summary["star_path"],
                particle_count=summary["particle_count"],
                apix=input_data.apix,
                box_size=input_data.box_size,
                edge_width=input_data.edge_width,
                micrograph_name=summary["micrograph_name"],
                source_micrograph_path=input_data.micrograph_path,
                # particle_stack_id stays None — TaskOutputProcessor will
                # write the artifact row + project the id back when
                # Phase 4 lands. Per rule 2 (immutability): plugins
                # never write the artifact row themselves.
                particle_stack_id=None,
                extras={"json_path": summary["json_path"]},
            )
        except Exception as exc:
            if step is not None:
                emit_step(step.failed(error=str(exc)))
            raise


def build_extraction_result(
    task: TaskMessage, output: ParticleExtractionOutput
) -> TaskResultMessage:
    """Wrap the extractor's output for the result queue."""
    files = [
        OutputFile(name=os.path.basename(output.mrcs_path), path=output.mrcs_path, required=True),
        OutputFile(name=os.path.basename(output.star_path), path=output.star_path, required=True),
    ]
    if "json_path" in output.extras:
        files.append(
            OutputFile(
                name=os.path.basename(output.extras["json_path"]),
                path=output.extras["json_path"],
                required=False,
            )
        )
    return TaskResultMessage(
        worker_instance_id=task.worker_instance_id,
        job_id=task.job_id,
        task_id=task.id,
        image_path=output.source_micrograph_path,
        session_id=task.session_id,
        session_name=task.session_name,
        code=200,
        message=f"Extracted {output.particle_count} particles",
        type=task.type,
        output_data={
            "mrcs_path": output.mrcs_path,
            "star_path": output.star_path,
            "particle_count": output.particle_count,
            "apix": output.apix,
            "box_size": output.box_size,
            **output.extras,
        },
        output_files=files,
    )


__all__ = [
    "StackMakerPlugin",
    "build_extraction_result",
]
