"""Resolve the Keras API the pre-trained MicAssess/2DAssess weights need.

The shipped ``.h5`` weights are Keras-2 era.  On TensorFlow >= 2.16 (which
bundles Keras 3) they only load through the ``tf-keras`` compatibility package,
and ``tensorflow.keras.preprocessing`` no longer exists.  This module picks
``tf-keras`` when available and falls back to the legacy ``tensorflow.keras``
namespace, so every model module imports its Keras symbols from one place.
"""

from __future__ import annotations

try:  # TensorFlow >= 2.16 / Keras 3 environments
    import tf_keras as _keras
except ImportError:  # older TensorFlow where tensorflow.keras is Keras 2
    from tensorflow import keras as _keras

backend = _keras.backend
metrics = _keras.metrics
load_model = _keras.models.load_model
Model = _keras.models.Model
Adam = _keras.optimizers.Adam
ImageDataGenerator = _keras.preprocessing.image.ImageDataGenerator

Input = _keras.layers.Input
Cropping2D = _keras.layers.Cropping2D
Concatenate = _keras.layers.Concatenate
Lambda = _keras.layers.Lambda
