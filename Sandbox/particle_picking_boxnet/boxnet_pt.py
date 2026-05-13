"""
BoxnetPT loader — ported from eval_micrograph/boxnet_utils.py with the
flexible_forward graph-trace patching kept intact.

This is the minimal viable port: the `flexible_forward` body is preserved
verbatim because it's the actual operator graph from the traced TF → PyTorch
conversion. Re-deriving it is out of scope; this wrapper just makes loading,
batching, and pad/unpad accessible to the picker and the ONNX exporter.
"""

import torch
import numpy as np
from numpy.typing import NDArray
from typing import Self


def flexible_forward(self, input_1):
    """
    Reattaches the original Warp BoxNet forward to the loaded traced module.

    The `.pt` is a graph-trace (saved with the entire module, not just
    weights), which means the original `forward()` is gone. This function
    walks the named submodules and reproduces the layer-by-layer dataflow
    that the TF source defined.
    """
    g = lambda name: getattr(self, name)  # noqa: E731

    x1 = g("batch_normalization/FusedBatchNorm;conv2d/Conv2D1")(input_1)
    x = g("LeakyRelu/Maximum;LeakyRelu/mul")(x1)
    c2 = g("conv2d_2/Conv2D1")(x)
    x = g("batch_normalization_2/FusedBatchNorm;conv2d_3/Conv2D")(x)
    x = g("LeakyRelu_1/Maximum;LeakyRelu_1/mul")(x)
    c4 = g("conv2d_4/Conv2D1")(x)
    a0 = self.add(c4, c2)
    a0 = g("batch_normalization_3/FusedBatchNorm")(a0, self.initializers.onnx_initializer_1)
    a0 = g("batch_normalization_3/FusedBatchNorm1")(a0, self.initializers.onnx_initializer_2)
    x = g("LeakyRelu_2/Maximum;LeakyRelu_2/mul")(a0)
    x = g("batch_normalization_4/FusedBatchNorm;conv2d_5/Conv2D")(x)
    x = g("LeakyRelu_3/Maximum;LeakyRelu_3/mul")(x)
    c6 = g("conv2d_6/Conv2D1")(x)
    a1 = self.add_1(c6, a0)
    a1 = g("batch_normalization_5/FusedBatchNorm")(a1, self.initializers.onnx_initializer_3)
    a1 = g("batch_normalization_5/FusedBatchNorm1")(a1, self.initializers.onnx_initializer_4)
    x = g("LeakyRelu_4/Maximum;LeakyRelu_4/mul")(a1)
    x = g("batch_normalization_6/FusedBatchNorm;conv2d_7/Conv2D")(x)
    x = g("LeakyRelu_5/Maximum;LeakyRelu_5/mul")(x)
    c8 = g("conv2d_8/Conv2D1")(x)
    a2 = self.add_2(c8, a1)
    a2 = g("batch_normalization_7/FusedBatchNorm")(a2, self.initializers.onnx_initializer_5)
    a2 = g("batch_normalization_7/FusedBatchNorm1")(a2, self.initializers.onnx_initializer_6)
    x = g("LeakyRelu_6/Maximum;LeakyRelu_6/mul")(a2)
    c9 = g("conv2d_9/Conv2D")(x)
    x = g("batch_normalization_8/FusedBatchNorm;conv2d_10/Conv2D")(x)
    x = g("LeakyRelu_7/Maximum;LeakyRelu_7/mul")(x)
    c11 = g("conv2d_11/Conv2D1")(x)
    a3 = self.add_3(c11, c9)
    a3 = g("batch_normalization_9/FusedBatchNorm")(a3, self.initializers.onnx_initializer_7)
    a3 = g("batch_normalization_9/FusedBatchNorm1")(a3, self.initializers.onnx_initializer_8)
    x = g("LeakyRelu_8/Maximum;LeakyRelu_8/mul")(a3)
    x = g("batch_normalization_10/FusedBatchNorm;conv2d_12/Conv2D")(x)
    x = g("LeakyRelu_9/Maximum;LeakyRelu_9/mul")(x)
    c13 = g("conv2d_13/Conv2D1")(x)
    a4 = self.add_4(c13, a3)
    a4 = g("batch_normalization_11/FusedBatchNorm")(a4, self.initializers.onnx_initializer_9)
    a4 = g("batch_normalization_11/FusedBatchNorm1")(a4, self.initializers.onnx_initializer_10)
    x = g("LeakyRelu_10/Maximum;LeakyRelu_10/mul")(a4)
    x = g("batch_normalization_12/FusedBatchNorm;conv2d_14/Conv2D")(x)
    x = g("LeakyRelu_11/Maximum;LeakyRelu_11/mul")(x)
    c15 = g("conv2d_15/Conv2D1")(x)
    a5 = self.add_5(c15, a4)
    a5 = g("batch_normalization_13/FusedBatchNorm")(a5, self.initializers.onnx_initializer_11)
    a5 = g("batch_normalization_13/FusedBatchNorm1")(a5, self.initializers.onnx_initializer_12)
    x = g("LeakyRelu_12/Maximum;LeakyRelu_12/mul")(a5)
    c16 = g("conv2d_16/Conv2D1")(x)
    x = g("batch_normalization_14/FusedBatchNorm;conv2d_17/Conv2D")(x)
    x = g("LeakyRelu_13/Maximum;LeakyRelu_13/mul")(x)
    c18 = g("conv2d_18/Conv2D1")(x)
    a6 = self.add_6(c18, c16)
    a6 = g("batch_normalization_15/FusedBatchNorm")(a6, self.initializers.onnx_initializer_13)
    a6 = g("batch_normalization_15/FusedBatchNorm1")(a6, self.initializers.onnx_initializer_14)
    x = g("LeakyRelu_14/Maximum;LeakyRelu_14/mul")(a6)
    x = g("batch_normalization_16/FusedBatchNorm;conv2d_19/Conv2D")(x)
    x = g("LeakyRelu_15/Maximum;LeakyRelu_15/mul")(x)
    c20 = g("conv2d_20/Conv2D1")(x)
    a7 = self.add_7(c20, a6)
    a7 = g("batch_normalization_17/FusedBatchNorm")(a7, self.initializers.onnx_initializer_15)
    a7 = g("batch_normalization_17/FusedBatchNorm1")(a7, self.initializers.onnx_initializer_16)
    x = g("LeakyRelu_16/Maximum;LeakyRelu_16/mul")(a7)
    x = g("batch_normalization_18/FusedBatchNorm;conv2d_21/Conv2D")(x)
    x = g("LeakyRelu_17/Maximum;LeakyRelu_17/mul")(x)
    c22 = g("conv2d_22/Conv2D1")(x)
    a8 = self.add_8(c22, a7)
    a8 = g("batch_normalization_19/FusedBatchNorm")(a8, self.initializers.onnx_initializer_17)
    a8 = g("batch_normalization_19/FusedBatchNorm1")(a8, self.initializers.onnx_initializer_18)
    x = g("LeakyRelu_18/Maximum;LeakyRelu_18/mul")(a8)
    c23 = g("conv2d_23/Conv2D1")(x)
    x = g("batch_normalization_20/FusedBatchNorm;conv2d_24/Conv2D")(x)
    x = g("LeakyRelu_19/Maximum;LeakyRelu_19/mul")(x)
    c25 = g("conv2d_25/Conv2D1")(x)
    a9 = self.add_9(c25, c23)
    a9 = g("batch_normalization_21/FusedBatchNorm")(a9, self.initializers.onnx_initializer_19)
    a9 = g("batch_normalization_21/FusedBatchNorm1")(a9, self.initializers.onnx_initializer_20)
    x = g("LeakyRelu_20/Maximum;LeakyRelu_20/mul")(a9)
    x = g("batch_normalization_22/FusedBatchNorm;conv2d_26/Conv2D")(x)
    x = g("LeakyRelu_21/Maximum;LeakyRelu_21/mul")(x)
    c27 = g("conv2d_27/Conv2D1")(x)
    a10 = self.add_10(c27, a9)
    a10 = g("batch_normalization_23/FusedBatchNorm")(a10, self.initializers.onnx_initializer_21)
    a10 = g("batch_normalization_23/FusedBatchNorm1")(a10, self.initializers.onnx_initializer_22)
    x = g("LeakyRelu_22/Maximum;LeakyRelu_22/mul")(a10)
    x = g("batch_normalization_24/FusedBatchNorm;conv2d_28/Conv2D")(x)
    x = g("LeakyRelu_23/Maximum;LeakyRelu_23/mul")(x)
    c29 = g("conv2d_29/Conv2D1")(x)
    a11 = self.add_11(c29, a10)
    a11 = g("batch_normalization_25/FusedBatchNorm")(a11, self.initializers.onnx_initializer_23)
    a11 = g("batch_normalization_25/FusedBatchNorm1")(a11, self.initializers.onnx_initializer_24)
    x = g("LeakyRelu_24/Maximum;LeakyRelu_24/mul")(a11)
    c30 = g("conv2d_30/Conv2D1")(x)
    x = g("batch_normalization_26/FusedBatchNorm;conv2d_31/Conv2D")(x)
    x = g("LeakyRelu_25/Maximum;LeakyRelu_25/mul")(x)
    c32 = g("conv2d_32/Conv2D1")(x)
    a12 = self.add_12(c32, c30)
    a12 = g("batch_normalization_27/FusedBatchNorm")(a12, self.initializers.onnx_initializer_25)
    a12 = g("batch_normalization_27/FusedBatchNorm1")(a12, self.initializers.onnx_initializer_26)
    x = g("LeakyRelu_26/Maximum;LeakyRelu_26/mul")(a12)
    x = g("batch_normalization_28/FusedBatchNorm;conv2d_33/Conv2D")(x)
    x = g("LeakyRelu_27/Maximum;LeakyRelu_27/mul")(x)
    c34 = g("conv2d_34/Conv2D1")(x)
    a13 = self.add_13(c34, a12)
    a13 = g("batch_normalization_29/FusedBatchNorm")(a13, self.initializers.onnx_initializer_27)
    a13 = g("batch_normalization_29/FusedBatchNorm1")(a13, self.initializers.onnx_initializer_28)
    x = g("LeakyRelu_28/Maximum;LeakyRelu_28/mul")(a13)
    x = g("batch_normalization_30/FusedBatchNorm;conv2d_35/Conv2D")(x)
    x = g("LeakyRelu_29/Maximum;LeakyRelu_29/mul")(x)
    c36 = g("conv2d_36/Conv2D1")(x)
    a14 = self.add_14(c36, a13)

    r1 = self.Resize__694(a14, self.initializers.onnx_initializer_29, self.initializers.onnx_initializer_30)
    cat2 = self.concat_2(a11, r1)
    cat2 = g("batch_normalization_39/FusedBatchNorm1")(cat2, self.initializers.onnx_initializer_31)
    cat2 = g("batch_normalization_39/FusedBatchNorm2")(cat2, self.initializers.onnx_initializer_32)
    x = g("LeakyRelu_38/Maximum;LeakyRelu_38/mul")(cat2)
    c49 = g("conv2d_49/Conv2D1")(x)
    x = g("batch_normalization_40/FusedBatchNorm;conv2d_50/Conv2D")(x)
    x = g("LeakyRelu_39/Maximum;LeakyRelu_39/mul")(x)
    c51 = g("conv2d_51/Conv2D1")(x)
    a19 = self.add_19(c51, c49)
    a19 = g("batch_normalization_41/FusedBatchNorm")(a19, self.initializers.onnx_initializer_33)
    a19 = g("batch_normalization_41/FusedBatchNorm1")(a19, self.initializers.onnx_initializer_34)
    x = g("LeakyRelu_40/Maximum;LeakyRelu_40/mul")(a19)
    x = g("batch_normalization_42/FusedBatchNorm;conv2d_52/Conv2D")(x)
    x = g("LeakyRelu_41/Maximum;LeakyRelu_41/mul")(x)
    c53 = g("conv2d_53/Conv2D1")(x)
    a20 = self.add_20(c53, a19)
    a20 = g("batch_normalization_43/FusedBatchNorm")(a20, self.initializers.onnx_initializer_35)
    a20 = g("batch_normalization_43/FusedBatchNorm1")(a20, self.initializers.onnx_initializer_36)
    x = g("LeakyRelu_42/Maximum;LeakyRelu_42/mul")(a20)
    x = g("batch_normalization_44/FusedBatchNorm;conv2d_54/Conv2D")(x)
    x = g("LeakyRelu_43/Maximum;LeakyRelu_43/mul")(x)
    c55 = g("conv2d_55/Conv2D1")(x)
    a21 = self.add_21(c55, a20)

    r2 = self.Resize__735(a21, self.initializers.onnx_initializer_37, self.initializers.onnx_initializer_38)
    cat3 = self.concat_3(a8, r2)
    cat3 = g("batch_normalization_45/FusedBatchNorm1")(cat3, self.initializers.onnx_initializer_39)
    cat3 = g("batch_normalization_45/FusedBatchNorm2")(cat3, self.initializers.onnx_initializer_40)
    x = g("LeakyRelu_44/Maximum;LeakyRelu_44/mul")(cat3)
    c56 = g("conv2d_56/Conv2D1")(x)
    x = g("batch_normalization_46/FusedBatchNorm;conv2d_57/Conv2D")(x)
    x = g("LeakyRelu_45/Maximum;LeakyRelu_45/mul")(x)
    c58 = g("conv2d_58/Conv2D1")(x)
    a22 = self.add_22(c58, c56)
    a22 = g("batch_normalization_47/FusedBatchNorm")(a22, self.initializers.onnx_initializer_41)
    a22 = g("batch_normalization_47/FusedBatchNorm1")(a22, self.initializers.onnx_initializer_42)
    x = g("LeakyRelu_46/Maximum;LeakyRelu_46/mul")(a22)
    x = g("batch_normalization_48/FusedBatchNorm;conv2d_59/Conv2D")(x)
    x = g("LeakyRelu_47/Maximum;LeakyRelu_47/mul")(x)
    c60 = g("conv2d_60/Conv2D1")(x)
    a23 = self.add_23(c60, a22)
    a23 = g("batch_normalization_49/FusedBatchNorm")(a23, self.initializers.onnx_initializer_43)
    a23 = g("batch_normalization_49/FusedBatchNorm1")(a23, self.initializers.onnx_initializer_44)
    x = g("LeakyRelu_48/Maximum;LeakyRelu_48/mul")(a23)
    x = g("batch_normalization_50/FusedBatchNorm;conv2d_61/Conv2D")(x)
    x = g("LeakyRelu_49/Maximum;LeakyRelu_49/mul")(x)
    c62 = g("conv2d_62/Conv2D1")(x)
    a24 = self.add_24(c62, a23)

    r3 = self.Resize__776(a24, self.initializers.onnx_initializer_45, self.initializers.onnx_initializer_46)
    cat4 = self.concat_4(a5, r3)
    cat4 = g("batch_normalization_51/FusedBatchNorm1")(cat4, self.initializers.onnx_initializer_47)
    cat4 = g("batch_normalization_51/FusedBatchNorm2")(cat4, self.initializers.onnx_initializer_48)
    x = g("LeakyRelu_50/Maximum;LeakyRelu_50/mul")(cat4)
    c63 = g("conv2d_63/Conv2D1")(x)
    x = g("batch_normalization_52/FusedBatchNorm;conv2d_64/Conv2D")(x)
    x = g("LeakyRelu_51/Maximum;LeakyRelu_51/mul")(x)
    c65 = g("conv2d_65/Conv2D1")(x)
    a25 = self.add_25(c65, c63)
    a25 = g("batch_normalization_53/FusedBatchNorm")(a25, self.initializers.onnx_initializer_49)
    a25 = g("batch_normalization_53/FusedBatchNorm1")(a25, self.initializers.onnx_initializer_50)
    x = g("LeakyRelu_52/Maximum;LeakyRelu_52/mul")(a25)
    x = g("batch_normalization_54/FusedBatchNorm;conv2d_66/Conv2D")(x)
    x = g("LeakyRelu_53/Maximum;LeakyRelu_53/mul")(x)
    c67 = g("conv2d_67/Conv2D1")(x)
    a26 = self.add_26(c67, a25)
    a26 = g("batch_normalization_55/FusedBatchNorm")(a26, self.initializers.onnx_initializer_51)
    a26 = g("batch_normalization_55/FusedBatchNorm1")(a26, self.initializers.onnx_initializer_52)
    x = g("LeakyRelu_54/Maximum;LeakyRelu_54/mul")(a26)
    x = g("batch_normalization_56/FusedBatchNorm;conv2d_68/Conv2D")(x)
    x = g("LeakyRelu_55/Maximum;LeakyRelu_55/mul")(x)
    c69 = g("conv2d_69/Conv2D1")(x)
    a27 = self.add_27(c69, a26)

    r4 = self.Resize__817(a27, self.initializers.onnx_initializer_53, self.initializers.onnx_initializer_54)
    cat5 = self.concat_5(a2, r4)
    cat5 = g("batch_normalization_57/FusedBatchNorm1")(cat5, self.initializers.onnx_initializer_55)
    cat5 = g("batch_normalization_57/FusedBatchNorm2")(cat5, self.initializers.onnx_initializer_56)
    x = g("LeakyRelu_56/Maximum;LeakyRelu_56/mul")(cat5)
    c70 = g("conv2d_70/Conv2D1")(x)
    x = g("batch_normalization_58/FusedBatchNorm;conv2d_71/Conv2D")(x)
    x = g("LeakyRelu_57/Maximum;LeakyRelu_57/mul")(x)
    c72 = g("conv2d_72/Conv2D1")(x)
    a28 = self.add_28(c72, c70)
    a28 = g("batch_normalization_59/FusedBatchNorm")(a28, self.initializers.onnx_initializer_57)
    a28 = g("batch_normalization_59/FusedBatchNorm1")(a28, self.initializers.onnx_initializer_58)
    x = g("LeakyRelu_58/Maximum;LeakyRelu_58/mul")(a28)
    x = g("batch_normalization_60/FusedBatchNorm;conv2d_73/Conv2D")(x)
    x = g("LeakyRelu_59/Maximum;LeakyRelu_59/mul")(x)
    c74 = g("conv2d_74/Conv2D1")(x)
    a29 = self.add_29(c74, a28)
    a29 = g("batch_normalization_61/FusedBatchNorm")(a29, self.initializers.onnx_initializer_59)
    a29 = g("batch_normalization_61/FusedBatchNorm1")(a29, self.initializers.onnx_initializer_60)
    x = g("LeakyRelu_60/Maximum;LeakyRelu_60/mul")(a29)
    x = g("batch_normalization_62/FusedBatchNorm;conv2d_75/Conv2D")(x)
    x = g("LeakyRelu_61/Maximum;LeakyRelu_61/mul")(x)
    c76 = g("conv2d_76/Conv2D1")(x)
    a30 = self.add_30(c76, a29)
    a30 = g("batch_normalization_63/FusedBatchNorm")(a30, self.initializers.onnx_initializer_61)
    a30 = g("batch_normalization_63/FusedBatchNorm1")(a30, self.initializers.onnx_initializer_62)
    x = g("LeakyRelu_62/Maximum;LeakyRelu_62/mul")(a30)
    x = g("batch_normalization_64/FusedBatchNorm;conv2d_77/Conv2D")(x)
    x = g("LeakyRelu_63/Maximum;LeakyRelu_63/mul")(x)
    c78 = g("conv2d_78/Conv2D1")(x)
    a31 = self.add_31(c78, a30)

    head = g("conv2d_79/BiasAdd;conv2d_79/Conv2D;conv2d_78/bias/read")(a31)
    head = self.Transpose__1500(head)
    head = self.Reshape(head, self.initializers.onnx_initializer_63)

    shape = self.Shape(head)
    shape = self.Shape__870(shape)
    out_shape_hint = g("softmax_tensor:0__874")(shape)
    sliced = self.Slice(shape, self.initializers.onnx_initializer_64, self.initializers.onnx_initializer_65)
    new_shape = self.concat_6(self.initializers.onnx_initializer_66, sliced)
    new_shape = g("Reshape_1;Reshape__873")(new_shape)
    reshaped = g("Reshape_1;Reshape")(head, new_shape)
    softmaxed = self.Softmax(reshaped)
    return g("softmax_tensor:0")(softmaxed, out_shape_hint)


def pad_to_unit_3d(img_3d_np, pad_unit=256):
    """Center-pads a (B, H, W) array up to a multiple of `pad_unit`."""
    H_orig, W_orig = img_3d_np.shape[1:]
    H_target = int(np.ceil(H_orig / pad_unit) * pad_unit)
    W_target = int(np.ceil(W_orig / pad_unit) * pad_unit)
    pad_top = (H_target - H_orig) // 2
    pad_left = (W_target - W_orig) // 2
    padded = np.zeros((len(img_3d_np), H_target, W_target), dtype=img_3d_np.dtype)
    padded[:, pad_top:pad_top + H_orig, pad_left:pad_left + W_orig] = img_3d_np
    return padded


def unpad_batch(nparray_4d, H, W):
    """Center-crop a (B, h, w, C) array back to (B, H, W, C)."""
    h, w = nparray_4d.shape[1:3]
    top = max((h - H) // 2, 0)
    left = max((w - W) // 2, 0)
    return nparray_4d[:, top:top + H, left:left + W, :]


class BoxnetPT:
    """
    Wrapper around the Warp BoxNet v2 graph-trace.

    Forward returns a (H, W, 3) array of per-pixel class probabilities
        channel 0 = background
        channel 1 = particle
        channel 2 = dirt
    in [0, 1] (softmax-normalised by the graph itself).
    """

    def __init__(self, model_path):
        self.model = torch.load(model_path, weights_only=False)
        setattr(self.model, 'forward',
                flexible_forward.__get__(self.model, type(self.model)))
        self.model.eval()
        self.device = "cpu"

    def to(self, device) -> Self:
        self.device = device
        self.model.to(self.device)
        return self

    def compute_batch(self, imgs: NDArray) -> NDArray:
        imgs = imgs.copy().astype(np.float32)
        H, W = imgs.shape[1:]

        # Per-image standardisation (mean 0, std 1)
        flat = imgs.reshape(-1, H * W)
        flat = (flat - flat.mean(axis=1, keepdims=True)) / \
               (flat.std(axis=1, keepdims=True) + 1e-8)
        imgs = flat.reshape((-1, H, W))

        padded = pad_to_unit_3d(imgs)

        inputs = torch.tensor(padded, dtype=torch.float32).unsqueeze(1).to(self.device)

        with torch.no_grad():
            outputs = self.model(inputs)

        # Output is (B*H*W, 3) softmax → reshape to (B, H_pad, W_pad, 3)
        outputs = outputs.cpu().numpy().reshape(*padded.shape, 3)
        return unpad_batch(outputs, H, W)

    def __call__(self, imgs: NDArray) -> NDArray:
        is_single = imgs.ndim == 2
        if is_single:
            imgs = np.array([imgs])
        result = self.compute_batch(imgs)
        if is_single:
            result = result[0]
        return result
