"""2DAssess model: build the class-average classifier and run inference.

2DAssess sorts RELION 2D class averages into four buckets.  The model ships
with a custom weighted categorical cross-entropy loss, so ``custom_objects``
must be supplied when loading the ``.h5`` file.
"""

from __future__ import annotations

from functools import partial, update_wrapper
from itertools import product

import numpy as np

from . import keras_compat as K

# 2DAssess output classes, in the model's output order.
CLASS_AVERAGE_LABELS = ("Clip", "Edge", "Good", "Noise")


def _wrapped_partial(func, *args, **kwargs):
    wrapped = partial(func, *args, **kwargs)
    update_wrapper(wrapped, func)
    return wrapped


def w_categorical_crossentropy(y_true, y_pred, weights):
    """Weighted categorical cross-entropy used to train the 2DAssess model.

    The weight matrix penalises confusions with the "Good" class so the model
    is conservative about labelling a class average as good.
    """

    backend = K.backend
    n_classes = len(weights)
    final_mask = backend.zeros_like(y_pred[:, 0])
    y_pred_max = backend.reshape(
        backend.max(y_pred, axis=1), (backend.shape(y_pred)[0], 1)
    )
    y_pred_max_mat = backend.cast(backend.equal(y_pred, y_pred_max), backend.floatx())
    for predicted, true in product(range(n_classes), range(n_classes)):
        final_mask += weights[true, predicted] * y_pred_max_mat[:, predicted] * y_true[:, true]
    return backend.categorical_crossentropy(y_true, y_pred) * final_mask


def _ncce_loss():
    """Build the named weighted-cross-entropy loss with its 4x4 weight matrix."""

    weights = np.ones((4, 4))
    weights[(0, 1, 3), 2] = 1.0
    weights[2, (0, 1, 3)] = 1.0
    return _wrapped_partial(w_categorical_crossentropy, weights=weights)


def build_model(model_path: str):
    """Load and compile the 2DAssess class-average classifier."""

    loss = _ncce_loss()
    model = K.load_model(
        model_path, custom_objects={"w_categorical_crossentropy": loss}
    )
    model.compile(
        optimizer=K.Adam(learning_rate=1e-4),
        loss=loss,
        metrics=[K.metrics.categorical_accuracy],
    )
    return model


def predict(images, model) -> np.ndarray:
    """Return the class-probability array for ``images`` (array or generator)."""

    return model.predict(images)


def class_average_generator(jpg_root: str, batch_size: int = 32):
    """Return a non-shuffling generator over the class-average JPEGs.

    ``jpg_root`` must hold a single sub-directory of images (the
    ``flow_from_directory`` one-class layout).
    """

    datagen = K.ImageDataGenerator(
        rescale=1.0 / 255,
        samplewise_center=True,
        samplewise_std_normalization=True,
    )
    return datagen.flow_from_directory(
        jpg_root,
        target_size=(256, 256),
        batch_size=batch_size,
        color_mode="grayscale",
        class_mode=None,
        shuffle=False,
        interpolation="lanczos",
    )
