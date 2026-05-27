"""SAM2 particle-picker plugin.

Exposes two call surfaces:

  * Standard SDK bus/SYNC path (execute / execute_sync) — full-image
    automatic mask generation; the operator sets thresholds and the plugin
    returns all mask centroids that pass the geometry filter.

  * Custom /click-pick endpoint (registered in main.py) — interactive
    single-click segmentation; the React canvas sends a prompt point and
    receives the mask centroid + polygon within one HTTP round-trip.

The image embedding produced on the first /click-pick call is cached for
10 minutes so successive clicks on the same micrograph skip the expensive
encoder pass.
"""
from __future__ import annotations

import logging
import os
from typing import List, Type

from magellon_sdk.base import PluginBase
from magellon_sdk.categories.outputs import ParticlePickingOutput
from magellon_sdk.models import OutputFile, PluginInfo, TaskMessage, TaskResultMessage
from magellon_sdk.models.manifest import (
    Capability,
    IsolationLevel,
    ResourceHints,
    Transport,
)
from magellon_sdk.progress import NullReporter, ProgressReporter
from magellon_sdk.runner import emit_step, make_step_reporter

from plugin.compute import auto_pick, click_pick
from plugin.events import STEP_NAME, get_publisher
from plugin.models import ClickPickRequest, ClickPickResult, Sam2PickInput

logger = logging.getLogger(__name__)


class Sam2Plugin(PluginBase[Sam2PickInput, ParticlePickingOutput]):
    """SAM2-based particle picker.

    Supports both batch auto-picking (SYNC capability → /execute) and
    interactive click-picking (custom /click-pick endpoint).  GPU is
    optional — the tiny model runs on CPU in ~3 s per image embedding.
    """

    task_category_name = "particle_picking"

    capabilities = [
        Capability.GPU_OPTIONAL,
        Capability.CPU_INTENSIVE,
        Capability.IDEMPOTENT,
        Capability.PROGRESS_REPORTING,
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
        memory_mb=4000,
        cpu_cores=2,
        typical_duration_seconds=30.0,
    )
    backend_id = "sam2-particle-picker"
    tags = ["sam2", "segment-anything", "particle-picking", "interactive", "cryo-em"]

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="SAM2 Particle Picker",
            version="1.0.0",
            developer="Behdad Khoshbin b.khoshbin@gmail.com",
            description=(
                "Segment Anything Model 2 (Meta, 2024) for cryo-EM particle picking. "
                "Supports interactive click-to-pick (single HTTP round-trip after "
                "first-image warm-up) and full-image automatic mask generation."
            ),
        )

    @classmethod
    def input_schema(cls) -> Type[Sam2PickInput]:
        return Sam2PickInput

    @classmethod
    def output_schema(cls) -> Type[ParticlePickingOutput]:
        return ParticlePickingOutput

    def check_requirements(self):
        from magellon_sdk.base import RequirementResult
        results = []
        try:
            import sam2  # noqa: F401
            results.append(RequirementResult(
                condition="sam2_package",
                result="success",
                message="segment-anything-2 package available",
            ))
        except ImportError:
            results.append(RequirementResult(
                condition="sam2_package",
                result="failure",
                message="segment-anything-2 not installed — run: pip install sam2",
            ))
        try:
            import torch  # noqa: F401
            results.append(RequirementResult(
                condition="torch",
                result="success",
                message="PyTorch available",
            ))
        except ImportError:
            results.append(RequirementResult(
                condition="torch",
                result="failure",
                message="PyTorch not installed — required for SAM2",
            ))
        return results

    # ------------------------------------------------------------------
    # Batch auto-pick  (SYNC capability → POST /execute)
    # ------------------------------------------------------------------

    def execute(
        self,
        input_data: Sam2PickInput,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> ParticlePickingOutput:
        if not input_data.image_path:
            raise ValueError("sam2-picker: image_path is required")

        step = make_step_reporter(STEP_NAME, get_publisher)
        if step:
            emit_step(step.started())
        try:
            if step:
                emit_step(step.progress(10.0, "loading model + embedding image"))

            result = auto_pick(
                image_path=input_data.image_path,
                model_variant=input_data.model_variant,
                stability_score_threshold=input_data.stability_score_threshold,
                predicted_iou_threshold=input_data.predicted_iou_threshold,
                image_pixel_size=input_data.image_pixel_size,
                particle_diameter_min_angstrom=input_data.particle_diameter_min_angstrom,
                particle_diameter_max_angstrom=input_data.particle_diameter_max_angstrom,
                min_circularity=input_data.min_circularity,
                output_dir=input_data.output_dir,
            )

            if step:
                emit_step(step.progress(95.0, f"found {result['num_particles']} particles"))
                emit_step(step.completed(output_files=[result["particles_json_path"]]))

            return ParticlePickingOutput(
                num_particles=result["num_particles"],
                particles_json_path=result["particles_json_path"],
                image_shape=result["image_shape"],
                picks=None,
            )
        except Exception as exc:
            if step:
                emit_step(step.failed(error=str(exc)))
            raise

    def execute_sync(self, input_data: Sam2PickInput) -> ParticlePickingOutput:
        return self.execute(input_data, reporter=NullReporter())

    # ------------------------------------------------------------------
    # Interactive single-click segmentation (custom /click-pick endpoint)
    # ------------------------------------------------------------------

    def click_segment(self, req: ClickPickRequest) -> ClickPickResult:
        """Called directly by the /click-pick FastAPI endpoint."""
        result = click_pick(
            image_path=req.image_path,
            click_points=[p.model_dump() for p in req.click_points],
            model_variant=req.model_variant,
            mask_threshold=req.mask_threshold,
        )
        return ClickPickResult(**result)

    # ------------------------------------------------------------------
    # PREVIEW capability (auto-pick with cached result for retune)
    # ------------------------------------------------------------------

    def preview(self, input_data: Sam2PickInput):
        from plugin.preview import run_preview
        return run_preview(input_data)

    def retune(self, preview_id: str, params):
        from plugin.preview import run_retune
        return run_retune(preview_id, params)

    def discard_preview(self, preview_id: str) -> bool:
        from plugin.preview import discard_preview
        return discard_preview(preview_id)


# ------------------------------------------------------------------
# Bus result factory
# ------------------------------------------------------------------

def build_pick_result(
    task: TaskMessage, output: ParticlePickingOutput
) -> TaskResultMessage:
    import uuid as _uuid
    files = []
    if output.particles_json_path:
        files.append(OutputFile(
            name=os.path.basename(output.particles_json_path),
            path=output.particles_json_path,
            required=True,
        ))
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
        message=f"SAM2 found {output.num_particles} particles",
        type=task.type,
        output_data={
            "num_particles": output.num_particles,
            "particles_json_path": output.particles_json_path,
            "image_shape": output.image_shape,
            "ipp_name": data.get("ipp_name", "SAM2-pick"),
            **output.extras,
        },
        output_files=files,
    )


__all__ = ["Sam2Plugin", "build_pick_result"]
