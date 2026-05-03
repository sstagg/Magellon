"""CAN classifier plugin — 2D classification by competitive Hebbian topology.

Phase 7 (2026-05-03). Category: TWO_D_CLASSIFICATION (code 4),
backend_id: can-classifier. Subject is a particle stack — one task per
stack (rule 7), not per image. Once Phase 3 lands subject_kind /
subject_id will move from explicit input fields to the TaskMessage
envelope.

Per ratified rule 1: bus carries class_averages_path /
assignments_csv_path / etc. as refs only — never inline file content.
Per rule 2 (immutability): a re-run produces a new artifact row, never
updates the previous one — the plugin doesn't manage that, the
projector does.
"""
from __future__ import annotations

import logging
import os
from typing import Type

from magellon_sdk.base import PluginBase
from magellon_sdk.categories.outputs import TwoDClassificationOutput
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
from magellon_sdk.models.tasks import TwoDClassificationInput
from magellon_sdk.progress import NullReporter, ProgressReporter
from magellon_sdk.runner import emit_step, make_step_reporter

from plugin.compute import classify_stack
from plugin.events import STEP_NAME, get_publisher

logger = logging.getLogger(__name__)


class CanClassifierPlugin(PluginBase[TwoDClassificationInput, TwoDClassificationOutput]):
    """Run CAN topology + MRA alignment on a particle stack."""

    capabilities = [
        Capability.GPU_REQUIRED,
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
    # Order-of-magnitude bigger than every other plugin: holds the
    # full particle stack in memory, runs torch on GPU (or CPU
    # fallback), and writes per-iteration class averages.
    resource_hints = ResourceHints(
        memory_mb=8000, cpu_cores=4, typical_duration_seconds=600.0
    )
    tags = ["2d-classification", "can-classifier", "cryo-em"]

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="CAN Classifier",
            version="0.1.0",
            developer="Behdad Khoshbin b.khoshbin@gmail.com",
            description=(
                "Competitive-Hebbian topology + MRA 2D classification on "
                "a RELION-style particle stack. Emits class averages, "
                "particle assignments, FRC summaries."
            ),
        )

    @classmethod
    def input_schema(cls) -> Type[TwoDClassificationInput]:
        return TwoDClassificationInput

    @classmethod
    def output_schema(cls) -> Type[TwoDClassificationOutput]:
        return TwoDClassificationOutput

    def execute(
        self,
        input_data: TwoDClassificationInput,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> TwoDClassificationOutput:
        step = make_step_reporter(STEP_NAME, get_publisher)
        if step is not None:
            emit_step(step.started())
        try:
            if step is not None:
                emit_step(step.progress(5.0, "preprocessing particles"))

            summary = classify_stack(
                mrcs_path=input_data.mrcs_path,
                star_path=input_data.star_path,
                output_dir=input_data.output_dir,
                apix=input_data.apix,
                num_classes=input_data.num_classes,
                num_presentations=input_data.num_presentations,
                align_iters=input_data.align_iters,
                threads=input_data.threads,
                can_threads=input_data.can_threads,
                compute_backend=input_data.compute_backend,
                max_particles=input_data.max_particles,
                invert=input_data.invert,
                write_aligned_stack=input_data.write_aligned_stack,
                engine_opts=input_data.engine_opts,
            )

            if step is not None:
                emit_step(
                    step.progress(
                        95.0,
                        f"{summary['num_classes_emitted']} classes from "
                        f"{summary['num_particles_classified']} particles",
                    )
                )
                output_files = [
                    summary["class_averages_path"],
                    summary["assignments_csv_path"],
                    summary["class_counts_csv_path"],
                ]
                emit_step(step.completed(output_files=output_files))

            return TwoDClassificationOutput(
                class_averages_path=summary["class_averages_path"],
                assignments_csv_path=summary["assignments_csv_path"],
                class_counts_csv_path=summary["class_counts_csv_path"],
                run_summary_path=summary.get("run_summary_path"),
                iteration_history_path=summary.get("iteration_history_path"),
                aligned_stack_path=summary.get("aligned_stack_path"),
                num_classes_emitted=summary["num_classes_emitted"],
                num_particles_classified=summary["num_particles_classified"],
                apix=summary.get("apix"),
                output_dir=summary.get("output_dir"),
                source_particle_stack_id=(
                    str(input_data.particle_stack_id) if input_data.particle_stack_id else None
                ),
            )
        except Exception as exc:
            if step is not None:
                emit_step(step.failed(error=str(exc)))
            raise


def build_classification_result(
    task: TaskMessage, output: TwoDClassificationOutput
) -> TaskResultMessage:
    """Wrap the classifier's output for the result queue."""
    files = [
        OutputFile(
            name=os.path.basename(output.class_averages_path),
            path=output.class_averages_path,
            required=True,
        ),
        OutputFile(
            name=os.path.basename(output.assignments_csv_path),
            path=output.assignments_csv_path,
            required=True,
        ),
        OutputFile(
            name=os.path.basename(output.class_counts_csv_path),
            path=output.class_counts_csv_path,
            required=True,
        ),
    ]
    if output.run_summary_path:
        files.append(
            OutputFile(
                name=os.path.basename(output.run_summary_path),
                path=output.run_summary_path,
                required=False,
            )
        )

    return TaskResultMessage(
        worker_instance_id=task.worker_instance_id,
        job_id=task.job_id,
        task_id=task.id,
        session_id=task.session_id,
        session_name=task.session_name,
        code=200,
        message=(
            f"Classified {output.num_particles_classified} particles into "
            f"{output.num_classes_emitted} classes"
        ),
        type=task.type,
        output_data={
            "class_averages_path": output.class_averages_path,
            "assignments_csv_path": output.assignments_csv_path,
            "class_counts_csv_path": output.class_counts_csv_path,
            "run_summary_path": output.run_summary_path,
            "iteration_history_path": output.iteration_history_path,
            "aligned_stack_path": output.aligned_stack_path,
            "num_classes_emitted": output.num_classes_emitted,
            "num_particles_classified": output.num_particles_classified,
            "source_particle_stack_id": output.source_particle_stack_id,
            **output.extras,
        },
        output_files=files,
    )


__all__ = [
    "CanClassifierPlugin",
    "build_classification_result",
]
