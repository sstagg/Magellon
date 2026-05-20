"""MicAssess hierarchical model: build the graph and run inference.

The pre-trained model is a base CNN whose features are concatenated with an
FFT radial-average branch, followed by three classifier heads:

* ``binary_head`` -- good vs. bad,
* ``good_head``   -- great vs. decent (only meaningful for "good" micrographs),
* ``bad_head``    -- the four bad sub-classes.

These functions are pure given a weights directory and image arrays; all
microscope/file orchestration lives in :mod:`cryoassess.cli`.
"""

from __future__ import annotations

import glob
import os
from typing import Tuple

import numpy as np
import tensorflow as tf

from . import keras_compat as K
from .fft_layer import radavg_logps_sigmoid

IMG_DIM = 494
_FEATURE_LENGTH = 247

# Detector -> model input width in pixels.
DETECTOR_WIDTH = {"K2": 512, "K3": 696}

# (detector, cutpos) -> Cropping2D ``cropping`` argument.  A detector/cutpos
# pair that is not a key here is unsupported and rejected up front, rather than
# leaving the crop tensor undefined as the original code did.
_CROP = {
    ("K2", "center"): ((0, 0), (9, 9)),
    ("K3", "left"): ((0, 0), (0, 202)),
    ("K3", "right"): ((0, 0), (202, 0)),
}


def detector_width(detector: str) -> int:
    """Return the model input width for ``detector``; raise on an unknown one."""

    try:
        return DETECTOR_WIDTH[detector]
    except KeyError:
        raise ValueError(
            f"unknown detector {detector!r}; expected one of {sorted(DETECTOR_WIDTH)}"
        ) from None


def _find_weight(model_dir: str, prefix: str) -> str:
    """Return the single weight file in ``model_dir`` starting with ``prefix``."""

    matches = sorted(glob.glob(os.path.join(model_dir, prefix + "*")))
    if not matches:
        raise FileNotFoundError(
            f"no MicAssess weight file matching {prefix!r}* found in {model_dir!r}"
        )
    return matches[0]


def build_models(
    model_dir: str,
    detector: str = "K2",
    cutpos: str = "center",
) -> Tuple[object, object, object, object]:
    """Build the base feature model and the three classifier heads.

    ``cutpos`` selects which region of the frame the base CNN sees: ``center``
    for K2, ``left`` or ``right`` for the two halves of a K3 frame.
    """

    if (detector, cutpos) not in _CROP:
        raise ValueError(
            f"unsupported detector/cutpos combination ({detector!r}, {cutpos!r}); "
            f"supported: {sorted(_CROP)}"
        )

    width = detector_width(detector)
    inputs = K.Input(shape=(IMG_DIM, width, 1))
    crop = K.Cropping2D(cropping=_CROP[(detector, cutpos)])(inputs)

    base = K.load_model(_find_weight(model_dir, "base_"))
    base = K.Model(base.inputs, base.layers[-2].output)
    cnn_features = base(crop, training=False)

    fft_features = K.Lambda(radavg_logps_sigmoid, name="f_features")(crop)
    fft_features = tf.reshape(fft_features, (tf.shape(inputs)[0], _FEATURE_LENGTH))

    features = K.Concatenate(axis=1)([cnn_features, fft_features])
    base_model = K.Model(inputs, features)

    binary_head = _load_head(model_dir, "fine_binary_", "binary_crossentropy")
    good_head = _load_head(model_dir, "fine_good_", "binary_crossentropy")
    bad_head = _load_head(
        model_dir, "fine_bad_", "categorical_crossentropy", K.metrics.categorical_accuracy
    )
    return base_model, binary_head, good_head, bad_head


def _load_head(model_dir: str, prefix: str, loss: str, metric: str = "accuracy"):
    """Load one frozen classifier head and compile it for inference."""

    head = K.load_model(_find_weight(model_dir, prefix))
    head.trainable = False
    head.compile(optimizer=K.Adam(learning_rate=5e-6), loss=loss, metrics=[metric])
    return head


def predict(images, base_model, binary_head, good_head, bad_head):
    """Run the hierarchical model and return ``(binary, good, bad)`` probabilities.

    ``images`` may be an array or a Keras generator -- anything ``predict``
    accepts.
    """

    features = base_model.predict(images)
    return (
        binary_head.predict(features),
        good_head.predict(features),
        bad_head.predict(features),
    )


def image_generator(png_root: str, detector: str = "K2", batch_size: int = 32):
    """Return a non-shuffling generator over the PNGs under ``png_root``.

    ``png_root`` must hold a single sub-directory of images, the one-class
    layout ``flow_from_directory`` expects.  Every image is normalised and
    circularly masked by :func:`cryoassess.core.preprocess_micrograph`.
    """

    from cryoassess.core.preprocessing import preprocess_micrograph

    datagen = K.ImageDataGenerator(preprocessing_function=preprocess_micrograph)
    return datagen.flow_from_directory(
        png_root,
        target_size=(IMG_DIM, detector_width(detector)),
        batch_size=batch_size,
        color_mode="grayscale",
        class_mode=None,
        shuffle=False,
    )


def predict_micrographs(
    png_root: str,
    model_dir: str,
    detector: str = "K2",
    batch_size: int = 32,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build the model(s) and return ``(binary, good, bad)`` probabilities.

    K2 uses one centre-cropped pass.  K3 runs the left and right halves of the
    frame separately and combines them: the binary head takes the stricter
    (minimum good-probability) vote, the fine heads are averaged.
    """

    if detector == "K2":
        models = build_models(model_dir, "K2", "center")
        return predict(image_generator(png_root, "K2", batch_size), *models)

    left = predict(
        image_generator(png_root, "K3", batch_size),
        *build_models(model_dir, "K3", "left"),
    )
    right = predict(
        image_generator(png_root, "K3", batch_size),
        *build_models(model_dir, "K3", "right"),
    )
    binary = np.minimum(left[0], right[0])
    good = np.mean([left[1], right[1]], axis=0)
    bad = np.mean([left[2], right[2]], axis=0)
    return binary, good, bad
