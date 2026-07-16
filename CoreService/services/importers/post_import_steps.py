from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class ActivityType(str, Enum):
    TRANSFER_FRAME = "transfer_frame"
    COPY_IMAGE = "copy_image"
    VALIDATE_INPUT = "validate_input"
    CONVERT_IMAGE = "convert_image"
    DISPATCH_ANALYSIS = "dispatch_analysis"


@dataclass
class ImportTaskContext:
    importer: Any
    task_dto: Any
    image_path: str | None = None
    results: dict[str, Any] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)

    def current_image_path(self) -> str | None:
        return self.image_path or getattr(self.task_dto, "image_path", None)

    def set_image_path(self, image_path: str) -> None:
        self.image_path = image_path
        if hasattr(self.task_dto, "image_path"):
            self.task_dto.image_path = image_path


class ImportTaskStep(Protocol):
    name: str
    activity_type: ActivityType

    def should_run(self, context: ImportTaskContext) -> bool:
        ...

    def skip_message(self, context: ImportTaskContext) -> str:
        ...

    def run(self, context: ImportTaskContext) -> None:
        ...


class ImportTaskActivity:
    name: str
    activity_type: ActivityType

    def should_run(self, context: ImportTaskContext) -> bool:
        return True

    def skip_message(self, context: ImportTaskContext) -> str:
        return f"Skipping {self.name}"


class TransferFrameStep(ImportTaskActivity):
    name = "transfer_frame"
    activity_type = ActivityType.TRANSFER_FRAME

    def run(self, context: ImportTaskContext) -> None:
        context.importer.transfer_frame(context.task_dto)
        context.results[self.name] = True


class CopyImageStep(ImportTaskActivity):
    name = "copy_image"
    activity_type = ActivityType.COPY_IMAGE

    def run(self, context: ImportTaskContext) -> None:
        context.importer.copy_image(context.task_dto)
        copied_path = getattr(context.task_dto, "image_path", None)
        if copied_path:
            context.set_image_path(copied_path)
        context.results[self.name] = True


class EnsureImageExistsStep(ImportTaskActivity):
    name = "ensure_image_exists"
    activity_type = ActivityType.VALIDATE_INPUT

    def run(self, context: ImportTaskContext) -> None:
        image_path = context.current_image_path()
        if not image_path or not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
        context.set_image_path(image_path)
        context.results[self.name] = True


class ConvertPngStep(ImportTaskActivity):
    name = "png"
    activity_type = ActivityType.CONVERT_IMAGE

    def run(self, context: ImportTaskContext) -> None:
        context.results[self.name] = context.importer.convert_image_to_png(
            context.current_image_path()
        )


class FftStep(ImportTaskActivity):
    name = "fft"
    activity_type = ActivityType.CONVERT_IMAGE

    def run(self, context: ImportTaskContext) -> None:
        context.results[self.name] = context.importer.compute_fft(
            context.current_image_path()
        )


class CtfDispatchStep(ImportTaskActivity):
    name = "ctf"
    activity_type = ActivityType.DISPATCH_ANALYSIS

    def run(self, context: ImportTaskContext) -> None:
        context.results[self.name] = context.importer.compute_ctf(
            context.current_image_path(),
            context.task_dto,
        )


class MotionCorDispatchStep(ImportTaskActivity):
    name = "motioncor"
    activity_type = ActivityType.DISPATCH_ANALYSIS

    def should_run(self, context: ImportTaskContext) -> bool:
        frame_name = getattr(context.task_dto, "frame_name", None)
        import logging
        logging.getLogger(__name__).info(
            "[MOTIONCOR-1] should_run check: frame_name=%r → will_run=%s",
            frame_name, bool(frame_name),
        )
        return bool(frame_name)

    def skip_message(self, context: ImportTaskContext) -> str:
        return "Skipping motion correction (no frame)"

    def run(self, context: ImportTaskContext) -> None:
        import logging
        log = logging.getLogger(__name__)
        image_path = context.current_image_path()
        frame_name = getattr(context.task_dto, "frame_name", None)
        frame_path = getattr(context.task_dto, "frame_path", None)
        log.info(
            "[MOTIONCOR-2] MotionCorDispatchStep.run: image_path=%r frame_name=%r frame_path=%r",
            image_path, frame_name, frame_path,
        )
        result = context.importer.compute_motioncor(image_path, context.task_dto)
        log.info("[MOTIONCOR-3] compute_motioncor returned: %r", result)
        context.results[self.name] = result


class TopazPickStep(ImportTaskActivity):
    name = "topaz_pick"
    activity_type = ActivityType.DISPATCH_ANALYSIS

    def run(self, context: ImportTaskContext) -> None:
        context.results[self.name] = context.importer.compute_topaz_pick(
            context.current_image_path(),
            context.task_dto,
        )


class TopazDenoiseStep(ImportTaskActivity):
    name = "topaz_denoise"
    activity_type = ActivityType.DISPATCH_ANALYSIS

    def run(self, context: ImportTaskContext) -> None:
        context.results[self.name] = context.importer.compute_topaz_denoise(
            context.current_image_path(),
            context.task_dto,
        )


@dataclass(frozen=True)
class ImportTaskRecipe:
    name: str
    steps: tuple[ImportTaskStep, ...]

    @property
    def activity_types(self) -> tuple[ActivityType, ...]:
        return tuple(step.activity_type for step in self.steps)

    @property
    def step_names(self) -> tuple[str, ...]:
        return tuple(step.name for step in self.steps)

    def has_activity_type(self, activity_type: ActivityType) -> bool:
        return activity_type in self.activity_types

    def describe(self) -> list[dict[str, str]]:
        return [
            {"name": step.name, "activity_type": step.activity_type.value}
            for step in self.steps
        ]


class ImportTaskPipeline:
    """Template for per-image post-import work.

    Importers choose strategies by composing steps. The common order stays in
    one place while source-specific importers decide which optional steps apply.
    """

    def __init__(self, recipe: ImportTaskRecipe):
        self.recipe = recipe
        self.steps = list(recipe.steps)

    def run(self, importer: Any, task_dto: Any, *, image_path: str | None = None) -> ImportTaskContext:
        context = ImportTaskContext(importer=importer, task_dto=task_dto, image_path=image_path)
        if image_path:
            context.set_image_path(image_path)
        for step in self.steps:
            if not step.should_run(context):
                message = step.skip_message(context)
                context.skipped[step.name] = message
                context.results[step.name] = {"status": "skipped", "message": message}
                continue
            step.run(context)
        return context


def build_standard_import_task_pipeline(
    *,
    transfer_frame: bool = True,
    copy_image: bool = False,
    ctf: bool = True,
    motioncor: bool = True,
    topaz_pick: bool = False,
    topaz_denoise: bool = False,
) -> ImportTaskPipeline:
    return ImportTaskPipeline(
        build_standard_import_task_recipe(
            transfer_frame=transfer_frame,
            copy_image=copy_image,
            ctf=ctf,
            motioncor=motioncor,
            topaz_pick=topaz_pick,
            topaz_denoise=topaz_denoise,
        )
    )


def build_standard_import_task_recipe(
    *,
    transfer_frame: bool = True,
    copy_image: bool = False,
    ctf: bool = True,
    motioncor: bool = True,
    topaz_pick: bool = False,
    topaz_denoise: bool = False,
    name: str = "standard_import",
) -> ImportTaskRecipe:
    steps: list[ImportTaskStep] = []
    if transfer_frame:
        steps.append(TransferFrameStep())
    if copy_image:
        steps.append(CopyImageStep())
    steps.extend([EnsureImageExistsStep(), ConvertPngStep(), FftStep()])
    if ctf:
        steps.append(CtfDispatchStep())
    if motioncor:
        steps.append(MotionCorDispatchStep())
    if topaz_pick:
        steps.append(TopazPickStep())
    if topaz_denoise:
        steps.append(TopazDenoiseStep())
    return ImportTaskRecipe(name=name, steps=tuple(steps))


def build_epu_import_task_recipe(
    *,
    transfer_frame: bool,
    copy_image: bool,
) -> ImportTaskRecipe:
    return build_standard_import_task_recipe(
        name="epu_import",
        transfer_frame=transfer_frame,
        copy_image=copy_image,
        ctf=True,
        motioncor=False,
        topaz_pick=False,
        topaz_denoise=False,
    )


def build_serialem_exposure_task_recipe(
    *,
    copy_image: bool,
) -> ImportTaskRecipe:
    return build_standard_import_task_recipe(
        name="serialem_exposure_import",
        transfer_frame=True,
        copy_image=copy_image,
        ctf=True,
        motioncor=True,
        topaz_pick=False,
        topaz_denoise=False,
    )


def build_serialem_montage_task_recipe(
    *,
    copy_image: bool,
) -> ImportTaskRecipe:
    return build_standard_import_task_recipe(
        name="serialem_montage_import",
        transfer_frame=True,
        copy_image=copy_image,
        ctf=False,
        motioncor=False,
        topaz_pick=False,
        topaz_denoise=False,
    )
