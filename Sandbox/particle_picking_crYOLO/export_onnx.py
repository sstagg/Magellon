#!/usr/bin/env python
"""
Export the crYOLO general model to ONNX — STUB.

crYOLO ships its general models as Keras `.h5` files with a custom YOLOv2-
style head. The canonical export path is `tf2onnx` against the loaded Keras
model, with a fixed input spec matching the architecture (1024x1024x1).

Pseudocode (uncomment + verify once a working TF + crYOLO env is available):

    import tensorflow as tf
    import tf2onnx
    from cryolo.utils import load_keras_model

    model = load_keras_model("weights/gmodel_phosnet_202005_N63_c17.h5")
    spec = (tf.TensorSpec((1, 1024, 1024, 1), tf.float32, name="input"),)
    onnx_model, _ = tf2onnx.convert.from_keras(model, input_signature=spec, opset=17)
    with open("weights/cryolo_general.onnx", "wb") as f:
        f.write(onnx_model.SerializeToString())

Known gotchas to validate before treating this as done:

1. The post-processing (anchor decoding, NMS) is NOT part of the Keras model
   in older crYOLO versions — it lives in Python. The ONNX graph will return
   raw grid predictions; e2e_onnx_pick.py needs to replicate the decode.
2. crYOLO's STANDARD normalization and the optional low-pass filter live
   outside the graph as well; they must be applied to the input array before
   inference.
3. crYOLO 1.9 ships a refactored detection head — the decode logic may differ
   from 1.8.x. Pin the version once verified.
"""
import sys

if __name__ == "__main__":
    sys.stderr.write(
        "export_onnx.py for crYOLO is a stub. See module docstring for the\n"
        "tf2onnx path. Drop in a `.h5` general model, install crYOLO+tf2onnx,\n"
        "uncomment the body, and verify against parity_check.py.\n"
    )
    sys.exit(1)
