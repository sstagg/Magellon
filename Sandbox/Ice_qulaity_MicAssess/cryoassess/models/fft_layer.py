"""TensorFlow radial-average log-power-spectrum layer (the model's f-branch).

This is the in-graph equivalent of :mod:`cryoassess.core.fft_features`.  It is
kept separate from the numpy reference because it imports TensorFlow and is
only meaningful inside the Keras model graph.
"""

from __future__ import annotations

import tensorflow as tf


def _power_spectrum(x: tf.Tensor) -> tf.Tensor:
    x = tf.cast(x, tf.complex64)
    shifted = tf.signal.fftshift(tf.signal.fft2d(tf.signal.fftshift(x)))
    return tf.math.pow(tf.math.abs(shifted), 2)


def _radial_average(image: tf.Tensor) -> tf.Tensor:
    x0 = tf.cast(image.shape[2] / 2, tf.float32)
    y0 = tf.cast(image.shape[1] / 2, tf.float32)

    xx, yy = tf.meshgrid(tf.range(image.shape[2]), tf.range(image.shape[1]))
    distance = tf.math.sqrt(
        tf.math.square(tf.cast(xx, tf.float32) - x0)
        + tf.math.square(tf.cast(yy, tf.float32) - y0)
    )

    max_radius = tf.cast(
        tf.math.floordiv(tf.math.minimum(image.shape[2], image.shape[1]), 2),
        tf.float32,
    )
    radii = tf.linspace(1.0, max_radius, num=tf.cast(max_radius, tf.int32))

    def ring_mean(r: tf.Tensor) -> tf.Tensor:
        ring = (distance >= r - 0.5) & (distance < r + 0.5)
        return tf.reduce_mean(tf.boolean_mask(image, ring, axis=1), axis=1)

    return tf.transpose(tf.squeeze(tf.map_fn(ring_mean, radii)))


def radavg_logps_sigmoid(x: tf.Tensor) -> tf.Tensor:
    """Sigmoid-squashed radial average of the log power spectrum.

    Wired into the model as a ``Lambda`` layer; mirrors
    :func:`cryoassess.core.fft_features.radial_log_power_spectrum_sigmoid`.
    """

    log_ps = tf.math.log(_power_spectrum(x))
    return tf.math.sigmoid(_radial_average(log_ps))
