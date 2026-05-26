from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ImportTaskContext:
    importer: Any
    task_dto: Any
    image_path: str | None = None
    results: dict[str, Any] = field(default_factory=dict)

    def current_image_path(self) -> str | None:
        return self.image_path or getattr(self.task_dto, "image_path", None)

    def set_image_path(self, image_path: str) -> None:
        self.image_path = image_path
        if hasattr(self.task_dto, "image_path"):
            self.task_dto.image_path = image_path


class ImportTaskStep(Protocol):
    name: str

    def run(self, context: ImportTaskContext) -> None:
        ...


class TransferFrameStep:
    name = "transfer_frame"

    def run(self, context: ImportTaskContext) -> None:
        context.importer.transfer_frame(context.task_dto)
        context.results[self.name] = True


class CopyImageStep:
    name = "copy_image"

    def run(self, context: ImportTaskContext) -> None:
        context.importer.copy_image(context.task_dto)
        copied_path = getattr(context.task_dto, "image_path", None)
        if copied_path:
            context.set_image_path(copied_path)
        context.results[self.name] = True


class EnsureImageExistsStep:
    name = "ensure_image_exists"

    def run(self, context: ImportTaskContext) -> None:
        image_path = context.current_image_path()
        if not image_path or not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
        context.set_image_path(image_path)
        context.results[self.name] = True


class ConvertPngStep:
    name = "png"

    def run(self, context: ImportTaskContext) -> None:
        context.results[self.name] = context.importer.convert_image_to_png(
            context.current_image_path()
        )


class FftStep:
    name = "fft"

    def run(self, context: ImportTaskContext) -> None:
        context.results[self.name] = context.importer.compute_fft(
            context.current_image_path()
        )


class CtfDispatchStep:
    name = "ctf"

    def run(self, context: ImportTaskContext) -> None:
        context.results[self.name] = context.importer.compute_ctf(
            context.current_image_path(),
            context.task_dto,
        )


class MotionCorDispatchStep:
    name = "motioncor"

    def run(self, context: ImportTaskContext) -> None:
        if getattr(context.task_dto, "frame_name", None):
            context.results[self.name] = context.importer.compute_motioncor(
                context.current_image_path(),
                context.task_dto,
            )
        else:
            context.results[self.name] = {"message": "Skipping motion correction (no frame)"}


class TopazPickStep:
    name = "topaz_pick"

    def run(self, context: ImportTaskContext) -> None:
        context.results[self.name] = context.importer.compute_topaz_pick(
            context.current_image_path(),
            context.task_dto,
        )


class TopazDenoiseStep:
    name = "topaz_denoise"

    def run(self, context: ImportTaskContext) -> None:
        context.results[self.name] = context.importer.compute_topaz_denoise(
            context.current_image_path(),
            context.task_dto,
        )


class ImportTaskPipeline:
    """Template for per-image post-import work.

    Importers choose strategies by composing steps. The common order stays in
    one place while source-specific importers decide which optional steps apply.
    """

    def __init__(self, steps: list[ImportTaskStep]):
        self.steps = steps

    def run(self, importer: Any, task_dto: Any, *, image_path: str | None = None) -> ImportTaskContext:
        context = ImportTaskContext(importer=importer, task_dto=task_dto, image_path=image_path)
        if image_path:
            context.set_image_path(image_path)
        for step in self.steps:
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
    return ImportTaskPipeline(steps)
