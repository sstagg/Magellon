from __future__ import annotations

import numpy as np
import scipy.ndimage

import mrc_io
import multihole_template

read_mrc = mrc_io.read_mrc
TemplateConvolver = multihole_template.TemplateConvolver


def create_template(
    image_shape: tuple[int, int],
    template_filename: str,
    template_diameter: float,
    file_diameter: float,
    invert: bool = False,
    multiple: int = 1,
    spacing: float = 100.0,
    angle: float = 0.0,
) -> np.ndarray:
    template_image = read_mrc(template_filename)
    if template_image.ndim != 2:
        raise ValueError("Template image must be 2D")

    if invert:
        template_mid = (float(template_image.min()) + float(template_image.max())) / 2.0
        template_image = -template_image + 2.0 * template_mid

    scale = float(template_diameter) / float(file_diameter)
    convolver = TemplateConvolver()
    convolver.set_single_template(template_image)
    convolver.set_config(multiple, scale)
    convolver.set_square_unit_vector(spacing, angle)
    template_image = convolver.make_multi_template()

    shape = image_shape
    origshape = template_image.shape
    edgevalue = float(template_image[0, 0])
    template = np.full(shape, edgevalue, dtype=template_image.dtype)

    if shape[0] < origshape[0]:
        offset = int((origshape[0] - shape[0]) / 2.0)
        template_image = template_image[offset : offset + shape[0], :]
    if shape[1] < origshape[1]:
        offset = int((origshape[1] - shape[1]) / 2.0)
        template_image = template_image[:, offset : offset + shape[1]]

    origshape = template_image.shape
    offset = (int((shape[0] - origshape[0]) / 2.0), int((shape[1] - origshape[1]) / 2.0))
    template[offset[0] : offset[0] + origshape[0], offset[1] : offset[1] + origshape[1]] = template_image
    shift = (shape[0] / 2.0, shape[1] / 2.0)
    template = scipy.ndimage.shift(template, shift, mode="wrap")
    return template.astype(np.float32)
