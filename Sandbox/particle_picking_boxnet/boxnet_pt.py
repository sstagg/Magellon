"""
BoxnetPT loader — vendored verbatim from eval_micrograph/boxnet_utils.py.

The `flexible_forward` function below is the actual operator graph from the
traced TF → PyTorch conversion (via onnx2torch). Re-deriving or compacting
it changes the dataflow — an earlier "readable" refactor produced wildly
wrong masks (particle_mean=0.0 vs the reference 0.023). Keep it verbatim.
"""

import torch
import numpy as np
from numpy.typing import NDArray
from typing import Self


def flexible_forward(self, input_1):
    batch_normalization_fused_batch_norm_conv2d_conv2d1 = getattr(self,
                                                                  "batch_normalization/FusedBatchNorm;conv2d/Conv2D1")(
        input_1);
    leaky_relu_maximum_leaky_relu_mul = getattr(self, "LeakyRelu/Maximum;LeakyRelu/mul")(
        batch_normalization_fused_batch_norm_conv2d_conv2d1);
    conv2d_2_conv2d1 = getattr(self, "conv2d_2/Conv2D1")(leaky_relu_maximum_leaky_relu_mul)
    batch_normalization_2_fused_batch_norm_conv2d_3_conv2d = getattr(self,
                                                                     "batch_normalization_2/FusedBatchNorm;conv2d_3/Conv2D")(
        leaky_relu_maximum_leaky_relu_mul);
    leaky_relu_1_maximum_leaky_relu_1_mul = getattr(self, "LeakyRelu_1/Maximum;LeakyRelu_1/mul")(
        batch_normalization_2_fused_batch_norm_conv2d_3_conv2d);
    conv2d_4_conv2d1 = getattr(self, "conv2d_4/Conv2D1")(leaky_relu_1_maximum_leaky_relu_1_mul);
    add = self.add(conv2d_4_conv2d1, conv2d_2_conv2d1);
    batch_normalization_3_fused_batch_norm = getattr(self, "batch_normalization_3/FusedBatchNorm")(add,
                                                                                                   self.initializers.onnx_initializer_1);
    batch_normalization_3_fused_batch_norm1 = getattr(self, "batch_normalization_3/FusedBatchNorm1")(
        batch_normalization_3_fused_batch_norm, self.initializers.onnx_initializer_2);
    leaky_relu_2_maximum_leaky_relu_2_mul = getattr(self, "LeakyRelu_2/Maximum;LeakyRelu_2/mul")(
        batch_normalization_3_fused_batch_norm1);
    batch_normalization_4_fused_batch_norm_conv2d_5_conv2d = getattr(self,
                                                                     "batch_normalization_4/FusedBatchNorm;conv2d_5/Conv2D")(
        leaky_relu_2_maximum_leaky_relu_2_mul);
    leaky_relu_3_maximum_leaky_relu_3_mul = getattr(self, "LeakyRelu_3/Maximum;LeakyRelu_3/mul")(
        batch_normalization_4_fused_batch_norm_conv2d_5_conv2d);
    conv2d_6_conv2d1 = getattr(self, "conv2d_6/Conv2D1")(leaky_relu_3_maximum_leaky_relu_3_mul);
    add_1 = self.add_1(conv2d_6_conv2d1, add);
    batch_normalization_5_fused_batch_norm = getattr(self, "batch_normalization_5/FusedBatchNorm")(add_1,
                                                                                                   self.initializers.onnx_initializer_3);
    batch_normalization_5_fused_batch_norm1 = getattr(self, "batch_normalization_5/FusedBatchNorm1")(
        batch_normalization_5_fused_batch_norm, self.initializers.onnx_initializer_4);
    leaky_relu_4_maximum_leaky_relu_4_mul = getattr(self, "LeakyRelu_4/Maximum;LeakyRelu_4/mul")(
        batch_normalization_5_fused_batch_norm1);
    batch_normalization_6_fused_batch_norm_conv2d_7_conv2d = getattr(self,
                                                                     "batch_normalization_6/FusedBatchNorm;conv2d_7/Conv2D")(
        leaky_relu_4_maximum_leaky_relu_4_mul);
    leaky_relu_5_maximum_leaky_relu_5_mul = getattr(self, "LeakyRelu_5/Maximum;LeakyRelu_5/mul")(
        batch_normalization_6_fused_batch_norm_conv2d_7_conv2d);
    conv2d_8_conv2d1 = getattr(self, "conv2d_8/Conv2D1")(leaky_relu_5_maximum_leaky_relu_5_mul);
    add_2 = self.add_2(conv2d_8_conv2d1, add_1);
    batch_normalization_7_fused_batch_norm = getattr(self, "batch_normalization_7/FusedBatchNorm")(add_2,
                                                                                                   self.initializers.onnx_initializer_5);
    batch_normalization_7_fused_batch_norm1 = getattr(self, "batch_normalization_7/FusedBatchNorm1")(
        batch_normalization_7_fused_batch_norm, self.initializers.onnx_initializer_6);
    leaky_relu_6_maximum_leaky_relu_6_mul = getattr(self, "LeakyRelu_6/Maximum;LeakyRelu_6/mul")(
        batch_normalization_7_fused_batch_norm1);
    conv2d_9_conv2d = getattr(self, "conv2d_9/Conv2D")(leaky_relu_6_maximum_leaky_relu_6_mul)
    batch_normalization_8_fused_batch_norm_conv2d_10_conv2d = getattr(self,
                                                                      "batch_normalization_8/FusedBatchNorm;conv2d_10/Conv2D")(
        leaky_relu_6_maximum_leaky_relu_6_mul);
    leaky_relu_7_maximum_leaky_relu_7_mul = getattr(self, "LeakyRelu_7/Maximum;LeakyRelu_7/mul")(
        batch_normalization_8_fused_batch_norm_conv2d_10_conv2d);
    conv2d_11_conv2d1 = getattr(self, "conv2d_11/Conv2D1")(leaky_relu_7_maximum_leaky_relu_7_mul);
    add_3 = self.add_3(conv2d_11_conv2d1, conv2d_9_conv2d);
    batch_normalization_9_fused_batch_norm = getattr(self, "batch_normalization_9/FusedBatchNorm")(add_3,
                                                                                                   self.initializers.onnx_initializer_7);
    batch_normalization_9_fused_batch_norm1 = getattr(self, "batch_normalization_9/FusedBatchNorm1")(
        batch_normalization_9_fused_batch_norm, self.initializers.onnx_initializer_8);
    leaky_relu_8_maximum_leaky_relu_8_mul = getattr(self, "LeakyRelu_8/Maximum;LeakyRelu_8/mul")(
        batch_normalization_9_fused_batch_norm1);
    batch_normalization_10_fused_batch_norm_conv2d_12_conv2d = getattr(self,
                                                                       "batch_normalization_10/FusedBatchNorm;conv2d_12/Conv2D")(
        leaky_relu_8_maximum_leaky_relu_8_mul);
    leaky_relu_9_maximum_leaky_relu_9_mul = getattr(self, "LeakyRelu_9/Maximum;LeakyRelu_9/mul")(
        batch_normalization_10_fused_batch_norm_conv2d_12_conv2d);
    conv2d_13_conv2d1 = getattr(self, "conv2d_13/Conv2D1")(leaky_relu_9_maximum_leaky_relu_9_mul);
    add_4 = self.add_4(conv2d_13_conv2d1, add_3);
    batch_normalization_11_fused_batch_norm = getattr(self, "batch_normalization_11/FusedBatchNorm")(add_4,
                                                                                                     self.initializers.onnx_initializer_9);
    batch_normalization_11_fused_batch_norm1 = getattr(self, "batch_normalization_11/FusedBatchNorm1")(
        batch_normalization_11_fused_batch_norm, self.initializers.onnx_initializer_10);
    leaky_relu_10_maximum_leaky_relu_10_mul = getattr(self, "LeakyRelu_10/Maximum;LeakyRelu_10/mul")(
        batch_normalization_11_fused_batch_norm1);
    batch_normalization_12_fused_batch_norm_conv2d_14_conv2d = getattr(self,
                                                                       "batch_normalization_12/FusedBatchNorm;conv2d_14/Conv2D")(
        leaky_relu_10_maximum_leaky_relu_10_mul);
    leaky_relu_11_maximum_leaky_relu_11_mul = getattr(self, "LeakyRelu_11/Maximum;LeakyRelu_11/mul")(
        batch_normalization_12_fused_batch_norm_conv2d_14_conv2d);
    conv2d_15_conv2d1 = getattr(self, "conv2d_15/Conv2D1")(leaky_relu_11_maximum_leaky_relu_11_mul);
    add_5 = self.add_5(conv2d_15_conv2d1, add_4);
    batch_normalization_13_fused_batch_norm = getattr(self, "batch_normalization_13/FusedBatchNorm")(add_5,
                                                                                                     self.initializers.onnx_initializer_11);
    batch_normalization_13_fused_batch_norm1 = getattr(self, "batch_normalization_13/FusedBatchNorm1")(
        batch_normalization_13_fused_batch_norm, self.initializers.onnx_initializer_12);
    leaky_relu_12_maximum_leaky_relu_12_mul = getattr(self, "LeakyRelu_12/Maximum;LeakyRelu_12/mul")(
        batch_normalization_13_fused_batch_norm1);
    conv2d_16_conv2d1 = getattr(self, "conv2d_16/Conv2D1")(leaky_relu_12_maximum_leaky_relu_12_mul)
    batch_normalization_14_fused_batch_norm_conv2d_17_conv2d = getattr(self,
                                                                       "batch_normalization_14/FusedBatchNorm;conv2d_17/Conv2D")(
        leaky_relu_12_maximum_leaky_relu_12_mul);
    leaky_relu_13_maximum_leaky_relu_13_mul = getattr(self, "LeakyRelu_13/Maximum;LeakyRelu_13/mul")(
        batch_normalization_14_fused_batch_norm_conv2d_17_conv2d);
    conv2d_18_conv2d1 = getattr(self, "conv2d_18/Conv2D1")(leaky_relu_13_maximum_leaky_relu_13_mul);
    add_6 = self.add_6(conv2d_18_conv2d1, conv2d_16_conv2d1);
    batch_normalization_15_fused_batch_norm = getattr(self, "batch_normalization_15/FusedBatchNorm")(add_6,
                                                                                                     self.initializers.onnx_initializer_13);
    batch_normalization_15_fused_batch_norm1 = getattr(self, "batch_normalization_15/FusedBatchNorm1")(
        batch_normalization_15_fused_batch_norm, self.initializers.onnx_initializer_14);
    leaky_relu_14_maximum_leaky_relu_14_mul = getattr(self, "LeakyRelu_14/Maximum;LeakyRelu_14/mul")(
        batch_normalization_15_fused_batch_norm1);
    batch_normalization_16_fused_batch_norm_conv2d_19_conv2d = getattr(self,
                                                                       "batch_normalization_16/FusedBatchNorm;conv2d_19/Conv2D")(
        leaky_relu_14_maximum_leaky_relu_14_mul);
    leaky_relu_15_maximum_leaky_relu_15_mul = getattr(self, "LeakyRelu_15/Maximum;LeakyRelu_15/mul")(
        batch_normalization_16_fused_batch_norm_conv2d_19_conv2d);
    conv2d_20_conv2d1 = getattr(self, "conv2d_20/Conv2D1")(leaky_relu_15_maximum_leaky_relu_15_mul);
    add_7 = self.add_7(conv2d_20_conv2d1, add_6);
    batch_normalization_17_fused_batch_norm = getattr(self, "batch_normalization_17/FusedBatchNorm")(add_7,
                                                                                                     self.initializers.onnx_initializer_15);
    batch_normalization_17_fused_batch_norm1 = getattr(self, "batch_normalization_17/FusedBatchNorm1")(
        batch_normalization_17_fused_batch_norm, self.initializers.onnx_initializer_16);
    leaky_relu_16_maximum_leaky_relu_16_mul = getattr(self, "LeakyRelu_16/Maximum;LeakyRelu_16/mul")(
        batch_normalization_17_fused_batch_norm1);
    batch_normalization_18_fused_batch_norm_conv2d_21_conv2d = getattr(self,
                                                                       "batch_normalization_18/FusedBatchNorm;conv2d_21/Conv2D")(
        leaky_relu_16_maximum_leaky_relu_16_mul);
    leaky_relu_17_maximum_leaky_relu_17_mul = getattr(self, "LeakyRelu_17/Maximum;LeakyRelu_17/mul")(
        batch_normalization_18_fused_batch_norm_conv2d_21_conv2d);
    conv2d_22_conv2d1 = getattr(self, "conv2d_22/Conv2D1")(leaky_relu_17_maximum_leaky_relu_17_mul);
    add_8 = self.add_8(conv2d_22_conv2d1, add_7);
    batch_normalization_19_fused_batch_norm = getattr(self, "batch_normalization_19/FusedBatchNorm")(add_8,
                                                                                                     self.initializers.onnx_initializer_17);
    batch_normalization_19_fused_batch_norm1 = getattr(self, "batch_normalization_19/FusedBatchNorm1")(
        batch_normalization_19_fused_batch_norm, self.initializers.onnx_initializer_18);
    leaky_relu_18_maximum_leaky_relu_18_mul = getattr(self, "LeakyRelu_18/Maximum;LeakyRelu_18/mul")(
        batch_normalization_19_fused_batch_norm1);
    conv2d_23_conv2d1 = getattr(self, "conv2d_23/Conv2D1")(leaky_relu_18_maximum_leaky_relu_18_mul)
    batch_normalization_20_fused_batch_norm_conv2d_24_conv2d = getattr(self,
                                                                       "batch_normalization_20/FusedBatchNorm;conv2d_24/Conv2D")(
        leaky_relu_18_maximum_leaky_relu_18_mul);
    leaky_relu_19_maximum_leaky_relu_19_mul = getattr(self, "LeakyRelu_19/Maximum;LeakyRelu_19/mul")(
        batch_normalization_20_fused_batch_norm_conv2d_24_conv2d);
    conv2d_25_conv2d1 = getattr(self, "conv2d_25/Conv2D1")(leaky_relu_19_maximum_leaky_relu_19_mul);
    add_9 = self.add_9(conv2d_25_conv2d1, conv2d_23_conv2d1);
    batch_normalization_21_fused_batch_norm = getattr(self, "batch_normalization_21/FusedBatchNorm")(add_9,
                                                                                                     self.initializers.onnx_initializer_19);
    batch_normalization_21_fused_batch_norm1 = getattr(self, "batch_normalization_21/FusedBatchNorm1")(
        batch_normalization_21_fused_batch_norm, self.initializers.onnx_initializer_20);
    leaky_relu_20_maximum_leaky_relu_20_mul = getattr(self, "LeakyRelu_20/Maximum;LeakyRelu_20/mul")(
        batch_normalization_21_fused_batch_norm1);
    batch_normalization_22_fused_batch_norm_conv2d_26_conv2d = getattr(self,
                                                                       "batch_normalization_22/FusedBatchNorm;conv2d_26/Conv2D")(
        leaky_relu_20_maximum_leaky_relu_20_mul);
    leaky_relu_21_maximum_leaky_relu_21_mul = getattr(self, "LeakyRelu_21/Maximum;LeakyRelu_21/mul")(
        batch_normalization_22_fused_batch_norm_conv2d_26_conv2d);
    conv2d_27_conv2d1 = getattr(self, "conv2d_27/Conv2D1")(leaky_relu_21_maximum_leaky_relu_21_mul);
    add_10 = self.add_10(conv2d_27_conv2d1, add_9);
    batch_normalization_23_fused_batch_norm = getattr(self, "batch_normalization_23/FusedBatchNorm")(add_10,
                                                                                                     self.initializers.onnx_initializer_21);
    batch_normalization_23_fused_batch_norm1 = getattr(self, "batch_normalization_23/FusedBatchNorm1")(
        batch_normalization_23_fused_batch_norm, self.initializers.onnx_initializer_22);
    leaky_relu_22_maximum_leaky_relu_22_mul = getattr(self, "LeakyRelu_22/Maximum;LeakyRelu_22/mul")(
        batch_normalization_23_fused_batch_norm1);
    batch_normalization_24_fused_batch_norm_conv2d_28_conv2d = getattr(self,
                                                                       "batch_normalization_24/FusedBatchNorm;conv2d_28/Conv2D")(
        leaky_relu_22_maximum_leaky_relu_22_mul);
    leaky_relu_23_maximum_leaky_relu_23_mul = getattr(self, "LeakyRelu_23/Maximum;LeakyRelu_23/mul")(
        batch_normalization_24_fused_batch_norm_conv2d_28_conv2d);
    conv2d_29_conv2d1 = getattr(self, "conv2d_29/Conv2D1")(leaky_relu_23_maximum_leaky_relu_23_mul);
    add_11 = self.add_11(conv2d_29_conv2d1, add_10);
    batch_normalization_25_fused_batch_norm = getattr(self, "batch_normalization_25/FusedBatchNorm")(add_11,
                                                                                                     self.initializers.onnx_initializer_23);
    batch_normalization_25_fused_batch_norm1 = getattr(self, "batch_normalization_25/FusedBatchNorm1")(
        batch_normalization_25_fused_batch_norm, self.initializers.onnx_initializer_24);
    leaky_relu_24_maximum_leaky_relu_24_mul = getattr(self, "LeakyRelu_24/Maximum;LeakyRelu_24/mul")(
        batch_normalization_25_fused_batch_norm1);
    conv2d_30_conv2d1 = getattr(self, "conv2d_30/Conv2D1")(leaky_relu_24_maximum_leaky_relu_24_mul)
    batch_normalization_26_fused_batch_norm_conv2d_31_conv2d = getattr(self,
                                                                       "batch_normalization_26/FusedBatchNorm;conv2d_31/Conv2D")(
        leaky_relu_24_maximum_leaky_relu_24_mul);
    leaky_relu_25_maximum_leaky_relu_25_mul = getattr(self, "LeakyRelu_25/Maximum;LeakyRelu_25/mul")(
        batch_normalization_26_fused_batch_norm_conv2d_31_conv2d);
    conv2d_32_conv2d1 = getattr(self, "conv2d_32/Conv2D1")(leaky_relu_25_maximum_leaky_relu_25_mul);
    add_12 = self.add_12(conv2d_32_conv2d1, conv2d_30_conv2d1);
    batch_normalization_27_fused_batch_norm = getattr(self, "batch_normalization_27/FusedBatchNorm")(add_12,
                                                                                                     self.initializers.onnx_initializer_25);
    batch_normalization_27_fused_batch_norm1 = getattr(self, "batch_normalization_27/FusedBatchNorm1")(
        batch_normalization_27_fused_batch_norm, self.initializers.onnx_initializer_26);
    leaky_relu_26_maximum_leaky_relu_26_mul = getattr(self, "LeakyRelu_26/Maximum;LeakyRelu_26/mul")(
        batch_normalization_27_fused_batch_norm1);
    batch_normalization_28_fused_batch_norm_conv2d_33_conv2d = getattr(self,
                                                                       "batch_normalization_28/FusedBatchNorm;conv2d_33/Conv2D")(
        leaky_relu_26_maximum_leaky_relu_26_mul);
    leaky_relu_27_maximum_leaky_relu_27_mul = getattr(self, "LeakyRelu_27/Maximum;LeakyRelu_27/mul")(
        batch_normalization_28_fused_batch_norm_conv2d_33_conv2d);
    conv2d_34_conv2d1 = getattr(self, "conv2d_34/Conv2D1")(leaky_relu_27_maximum_leaky_relu_27_mul);
    add_13 = self.add_13(conv2d_34_conv2d1, add_12);
    batch_normalization_29_fused_batch_norm = getattr(self, "batch_normalization_29/FusedBatchNorm")(add_13,
                                                                                                     self.initializers.onnx_initializer_27);
    batch_normalization_29_fused_batch_norm1 = getattr(self, "batch_normalization_29/FusedBatchNorm1")(
        batch_normalization_29_fused_batch_norm, self.initializers.onnx_initializer_28);
    leaky_relu_28_maximum_leaky_relu_28_mul = getattr(self, "LeakyRelu_28/Maximum;LeakyRelu_28/mul")(
        batch_normalization_29_fused_batch_norm1);
    batch_normalization_30_fused_batch_norm_conv2d_35_conv2d = getattr(self,
                                                                       "batch_normalization_30/FusedBatchNorm;conv2d_35/Conv2D")(
        leaky_relu_28_maximum_leaky_relu_28_mul);
    leaky_relu_29_maximum_leaky_relu_29_mul = getattr(self, "LeakyRelu_29/Maximum;LeakyRelu_29/mul")(
        batch_normalization_30_fused_batch_norm_conv2d_35_conv2d);
    conv2d_36_conv2d1 = getattr(self, "conv2d_36/Conv2D1")(leaky_relu_29_maximum_leaky_relu_29_mul);
    add_14 = self.add_14(conv2d_36_conv2d1, add_13);
    resize__694 = self.Resize__694(add_14, self.initializers.onnx_initializer_29, self.initializers.onnx_initializer_30);
    concat_2 = self.concat_2(add_11, resize__694);
    batch_normalization_39_fused_batch_norm1 = getattr(self, "batch_normalization_39/FusedBatchNorm1")(concat_2,
                                                                                                       self.initializers.onnx_initializer_31);
    batch_normalization_39_fused_batch_norm2 = getattr(self, "batch_normalization_39/FusedBatchNorm2")(
        batch_normalization_39_fused_batch_norm1, self.initializers.onnx_initializer_32);
    leaky_relu_38_maximum_leaky_relu_38_mul = getattr(self, "LeakyRelu_38/Maximum;LeakyRelu_38/mul")(
        batch_normalization_39_fused_batch_norm2);
    conv2d_49_conv2d1 = getattr(self, "conv2d_49/Conv2D1")(leaky_relu_38_maximum_leaky_relu_38_mul)
    batch_normalization_40_fused_batch_norm_conv2d_50_conv2d = getattr(self,
                                                                       "batch_normalization_40/FusedBatchNorm;conv2d_50/Conv2D")(
        leaky_relu_38_maximum_leaky_relu_38_mul);
    leaky_relu_39_maximum_leaky_relu_39_mul = getattr(self, "LeakyRelu_39/Maximum;LeakyRelu_39/mul")(
        batch_normalization_40_fused_batch_norm_conv2d_50_conv2d);
    conv2d_51_conv2d1 = getattr(self, "conv2d_51/Conv2D1")(leaky_relu_39_maximum_leaky_relu_39_mul);
    add_19 = self.add_19(conv2d_51_conv2d1, conv2d_49_conv2d1);
    batch_normalization_41_fused_batch_norm = getattr(self, "batch_normalization_41/FusedBatchNorm")(add_19,
                                                                                                     self.initializers.onnx_initializer_33);
    batch_normalization_41_fused_batch_norm1 = getattr(self, "batch_normalization_41/FusedBatchNorm1")(
        batch_normalization_41_fused_batch_norm, self.initializers.onnx_initializer_34);
    leaky_relu_40_maximum_leaky_relu_40_mul = getattr(self, "LeakyRelu_40/Maximum;LeakyRelu_40/mul")(
        batch_normalization_41_fused_batch_norm1);
    batch_normalization_42_fused_batch_norm_conv2d_52_conv2d = getattr(self,
                                                                       "batch_normalization_42/FusedBatchNorm;conv2d_52/Conv2D")(
        leaky_relu_40_maximum_leaky_relu_40_mul);
    leaky_relu_41_maximum_leaky_relu_41_mul = getattr(self, "LeakyRelu_41/Maximum;LeakyRelu_41/mul")(
        batch_normalization_42_fused_batch_norm_conv2d_52_conv2d);
    conv2d_53_conv2d1 = getattr(self, "conv2d_53/Conv2D1")(leaky_relu_41_maximum_leaky_relu_41_mul);
    add_20 = self.add_20(conv2d_53_conv2d1, add_19);
    batch_normalization_43_fused_batch_norm = getattr(self, "batch_normalization_43/FusedBatchNorm")(add_20,
                                                                                                     self.initializers.onnx_initializer_35);
    batch_normalization_43_fused_batch_norm1 = getattr(self, "batch_normalization_43/FusedBatchNorm1")(
        batch_normalization_43_fused_batch_norm, self.initializers.onnx_initializer_36);
    leaky_relu_42_maximum_leaky_relu_42_mul = getattr(self, "LeakyRelu_42/Maximum;LeakyRelu_42/mul")(
        batch_normalization_43_fused_batch_norm1);
    batch_normalization_44_fused_batch_norm_conv2d_54_conv2d = getattr(self,
                                                                       "batch_normalization_44/FusedBatchNorm;conv2d_54/Conv2D")(
        leaky_relu_42_maximum_leaky_relu_42_mul);
    leaky_relu_43_maximum_leaky_relu_43_mul = getattr(self, "LeakyRelu_43/Maximum;LeakyRelu_43/mul")(
        batch_normalization_44_fused_batch_norm_conv2d_54_conv2d);
    conv2d_55_conv2d1 = getattr(self, "conv2d_55/Conv2D1")(leaky_relu_43_maximum_leaky_relu_43_mul);
    add_21 = self.add_21(conv2d_55_conv2d1, add_20);
    resize__735 = self.Resize__735(add_21, self.initializers.onnx_initializer_37, self.initializers.onnx_initializer_38);
    concat_3 = self.concat_3(add_8, resize__735);
    batch_normalization_45_fused_batch_norm1 = getattr(self, "batch_normalization_45/FusedBatchNorm1")(concat_3,
                                                                                                       self.initializers.onnx_initializer_39);
    batch_normalization_45_fused_batch_norm2 = getattr(self, "batch_normalization_45/FusedBatchNorm2")(
        batch_normalization_45_fused_batch_norm1, self.initializers.onnx_initializer_40);
    leaky_relu_44_maximum_leaky_relu_44_mul = getattr(self, "LeakyRelu_44/Maximum;LeakyRelu_44/mul")(
        batch_normalization_45_fused_batch_norm2);
    conv2d_56_conv2d1 = getattr(self, "conv2d_56/Conv2D1")(leaky_relu_44_maximum_leaky_relu_44_mul)
    batch_normalization_46_fused_batch_norm_conv2d_57_conv2d = getattr(self,
                                                                       "batch_normalization_46/FusedBatchNorm;conv2d_57/Conv2D")(
        leaky_relu_44_maximum_leaky_relu_44_mul);
    leaky_relu_45_maximum_leaky_relu_45_mul = getattr(self, "LeakyRelu_45/Maximum;LeakyRelu_45/mul")(
        batch_normalization_46_fused_batch_norm_conv2d_57_conv2d);
    conv2d_58_conv2d1 = getattr(self, "conv2d_58/Conv2D1")(leaky_relu_45_maximum_leaky_relu_45_mul);
    add_22 = self.add_22(conv2d_58_conv2d1, conv2d_56_conv2d1);
    batch_normalization_47_fused_batch_norm = getattr(self, "batch_normalization_47/FusedBatchNorm")(add_22,
                                                                                                     self.initializers.onnx_initializer_41);
    batch_normalization_47_fused_batch_norm1 = getattr(self, "batch_normalization_47/FusedBatchNorm1")(
        batch_normalization_47_fused_batch_norm, self.initializers.onnx_initializer_42);
    leaky_relu_46_maximum_leaky_relu_46_mul = getattr(self, "LeakyRelu_46/Maximum;LeakyRelu_46/mul")(
        batch_normalization_47_fused_batch_norm1);
    batch_normalization_48_fused_batch_norm_conv2d_59_conv2d = getattr(self,
                                                                       "batch_normalization_48/FusedBatchNorm;conv2d_59/Conv2D")(
        leaky_relu_46_maximum_leaky_relu_46_mul);
    leaky_relu_47_maximum_leaky_relu_47_mul = getattr(self, "LeakyRelu_47/Maximum;LeakyRelu_47/mul")(
        batch_normalization_48_fused_batch_norm_conv2d_59_conv2d);
    conv2d_60_conv2d1 = getattr(self, "conv2d_60/Conv2D1")(leaky_relu_47_maximum_leaky_relu_47_mul);
    add_23 = self.add_23(conv2d_60_conv2d1, add_22);
    batch_normalization_49_fused_batch_norm = getattr(self, "batch_normalization_49/FusedBatchNorm")(add_23,
                                                                                                     self.initializers.onnx_initializer_43);
    batch_normalization_49_fused_batch_norm1 = getattr(self, "batch_normalization_49/FusedBatchNorm1")(
        batch_normalization_49_fused_batch_norm, self.initializers.onnx_initializer_44);
    leaky_relu_48_maximum_leaky_relu_48_mul = getattr(self, "LeakyRelu_48/Maximum;LeakyRelu_48/mul")(
        batch_normalization_49_fused_batch_norm1);
    batch_normalization_50_fused_batch_norm_conv2d_61_conv2d = getattr(self,
                                                                       "batch_normalization_50/FusedBatchNorm;conv2d_61/Conv2D")(
        leaky_relu_48_maximum_leaky_relu_48_mul);
    leaky_relu_49_maximum_leaky_relu_49_mul = getattr(self, "LeakyRelu_49/Maximum;LeakyRelu_49/mul")(
        batch_normalization_50_fused_batch_norm_conv2d_61_conv2d);
    conv2d_62_conv2d1 = getattr(self, "conv2d_62/Conv2D1")(leaky_relu_49_maximum_leaky_relu_49_mul);
    add_24 = self.add_24(conv2d_62_conv2d1, add_23);
    resize__776 = self.Resize__776(add_24, self.initializers.onnx_initializer_45, self.initializers.onnx_initializer_46);
    concat_4 = self.concat_4(add_5, resize__776);
    batch_normalization_51_fused_batch_norm1 = getattr(self, "batch_normalization_51/FusedBatchNorm1")(concat_4,
                                                                                                       self.initializers.onnx_initializer_47);
    batch_normalization_51_fused_batch_norm2 = getattr(self, "batch_normalization_51/FusedBatchNorm2")(
        batch_normalization_51_fused_batch_norm1, self.initializers.onnx_initializer_48);
    leaky_relu_50_maximum_leaky_relu_50_mul = getattr(self, "LeakyRelu_50/Maximum;LeakyRelu_50/mul")(
        batch_normalization_51_fused_batch_norm2);
    conv2d_63_conv2d1 = getattr(self, "conv2d_63/Conv2D1")(leaky_relu_50_maximum_leaky_relu_50_mul)
    batch_normalization_52_fused_batch_norm_conv2d_64_conv2d = getattr(self,
                                                                       "batch_normalization_52/FusedBatchNorm;conv2d_64/Conv2D")(
        leaky_relu_50_maximum_leaky_relu_50_mul);
    leaky_relu_51_maximum_leaky_relu_51_mul = getattr(self, "LeakyRelu_51/Maximum;LeakyRelu_51/mul")(
        batch_normalization_52_fused_batch_norm_conv2d_64_conv2d);
    conv2d_65_conv2d1 = getattr(self, "conv2d_65/Conv2D1")(leaky_relu_51_maximum_leaky_relu_51_mul);
    add_25 = self.add_25(conv2d_65_conv2d1, conv2d_63_conv2d1);
    batch_normalization_53_fused_batch_norm = getattr(self, "batch_normalization_53/FusedBatchNorm")(add_25,
                                                                                                     self.initializers.onnx_initializer_49);
    batch_normalization_53_fused_batch_norm1 = getattr(self, "batch_normalization_53/FusedBatchNorm1")(
        batch_normalization_53_fused_batch_norm, self.initializers.onnx_initializer_50);
    leaky_relu_52_maximum_leaky_relu_52_mul = getattr(self, "LeakyRelu_52/Maximum;LeakyRelu_52/mul")(
        batch_normalization_53_fused_batch_norm1);
    batch_normalization_54_fused_batch_norm_conv2d_66_conv2d = getattr(self,
                                                                       "batch_normalization_54/FusedBatchNorm;conv2d_66/Conv2D")(
        leaky_relu_52_maximum_leaky_relu_52_mul);
    leaky_relu_53_maximum_leaky_relu_53_mul = getattr(self, "LeakyRelu_53/Maximum;LeakyRelu_53/mul")(
        batch_normalization_54_fused_batch_norm_conv2d_66_conv2d);
    conv2d_67_conv2d1 = getattr(self, "conv2d_67/Conv2D1")(leaky_relu_53_maximum_leaky_relu_53_mul);
    add_26 = self.add_26(conv2d_67_conv2d1, add_25);
    batch_normalization_55_fused_batch_norm = getattr(self, "batch_normalization_55/FusedBatchNorm")(add_26,
                                                                                                     self.initializers.onnx_initializer_51);
    batch_normalization_55_fused_batch_norm1 = getattr(self, "batch_normalization_55/FusedBatchNorm1")(
        batch_normalization_55_fused_batch_norm, self.initializers.onnx_initializer_52);
    leaky_relu_54_maximum_leaky_relu_54_mul = getattr(self, "LeakyRelu_54/Maximum;LeakyRelu_54/mul")(
        batch_normalization_55_fused_batch_norm1);
    batch_normalization_56_fused_batch_norm_conv2d_68_conv2d = getattr(self,
                                                                       "batch_normalization_56/FusedBatchNorm;conv2d_68/Conv2D")(
        leaky_relu_54_maximum_leaky_relu_54_mul);
    leaky_relu_55_maximum_leaky_relu_55_mul = getattr(self, "LeakyRelu_55/Maximum;LeakyRelu_55/mul")(
        batch_normalization_56_fused_batch_norm_conv2d_68_conv2d);
    conv2d_69_conv2d1 = getattr(self, "conv2d_69/Conv2D1")(leaky_relu_55_maximum_leaky_relu_55_mul);
    add_27 = self.add_27(conv2d_69_conv2d1, add_26);
    resize__817 = self.Resize__817(add_27, self.initializers.onnx_initializer_53, self.initializers.onnx_initializer_54);
    concat_5 = self.concat_5(add_2, resize__817);
    batch_normalization_57_fused_batch_norm1 = getattr(self, "batch_normalization_57/FusedBatchNorm1")(concat_5,
                                                                                                       self.initializers.onnx_initializer_55);
    batch_normalization_57_fused_batch_norm2 = getattr(self, "batch_normalization_57/FusedBatchNorm2")(
        batch_normalization_57_fused_batch_norm1, self.initializers.onnx_initializer_56);
    leaky_relu_56_maximum_leaky_relu_56_mul = getattr(self, "LeakyRelu_56/Maximum;LeakyRelu_56/mul")(
        batch_normalization_57_fused_batch_norm2);
    conv2d_70_conv2d1 = getattr(self, "conv2d_70/Conv2D1")(leaky_relu_56_maximum_leaky_relu_56_mul)
    batch_normalization_58_fused_batch_norm_conv2d_71_conv2d = getattr(self,
                                                                       "batch_normalization_58/FusedBatchNorm;conv2d_71/Conv2D")(
        leaky_relu_56_maximum_leaky_relu_56_mul);
    leaky_relu_57_maximum_leaky_relu_57_mul = getattr(self, "LeakyRelu_57/Maximum;LeakyRelu_57/mul")(
        batch_normalization_58_fused_batch_norm_conv2d_71_conv2d);
    conv2d_72_conv2d1 = getattr(self, "conv2d_72/Conv2D1")(leaky_relu_57_maximum_leaky_relu_57_mul);
    add_28 = self.add_28(conv2d_72_conv2d1, conv2d_70_conv2d1);
    batch_normalization_59_fused_batch_norm = getattr(self, "batch_normalization_59/FusedBatchNorm")(add_28,
                                                                                                     self.initializers.onnx_initializer_57);
    batch_normalization_59_fused_batch_norm1 = getattr(self, "batch_normalization_59/FusedBatchNorm1")(
        batch_normalization_59_fused_batch_norm, self.initializers.onnx_initializer_58);
    leaky_relu_58_maximum_leaky_relu_58_mul = getattr(self, "LeakyRelu_58/Maximum;LeakyRelu_58/mul")(
        batch_normalization_59_fused_batch_norm1);
    batch_normalization_60_fused_batch_norm_conv2d_73_conv2d = getattr(self,
                                                                       "batch_normalization_60/FusedBatchNorm;conv2d_73/Conv2D")(
        leaky_relu_58_maximum_leaky_relu_58_mul);
    leaky_relu_59_maximum_leaky_relu_59_mul = getattr(self, "LeakyRelu_59/Maximum;LeakyRelu_59/mul")(
        batch_normalization_60_fused_batch_norm_conv2d_73_conv2d);
    conv2d_74_conv2d1 = getattr(self, "conv2d_74/Conv2D1")(leaky_relu_59_maximum_leaky_relu_59_mul);
    add_29 = self.add_29(conv2d_74_conv2d1, add_28);
    batch_normalization_61_fused_batch_norm = getattr(self, "batch_normalization_61/FusedBatchNorm")(add_29,
                                                                                                     self.initializers.onnx_initializer_59);
    batch_normalization_61_fused_batch_norm1 = getattr(self, "batch_normalization_61/FusedBatchNorm1")(
        batch_normalization_61_fused_batch_norm, self.initializers.onnx_initializer_60);
    leaky_relu_60_maximum_leaky_relu_60_mul = getattr(self, "LeakyRelu_60/Maximum;LeakyRelu_60/mul")(
        batch_normalization_61_fused_batch_norm1);
    batch_normalization_62_fused_batch_norm_conv2d_75_conv2d = getattr(self,
                                                                       "batch_normalization_62/FusedBatchNorm;conv2d_75/Conv2D")(
        leaky_relu_60_maximum_leaky_relu_60_mul);
    leaky_relu_61_maximum_leaky_relu_61_mul = getattr(self, "LeakyRelu_61/Maximum;LeakyRelu_61/mul")(
        batch_normalization_62_fused_batch_norm_conv2d_75_conv2d);
    conv2d_76_conv2d1 = getattr(self, "conv2d_76/Conv2D1")(leaky_relu_61_maximum_leaky_relu_61_mul);
    add_30 = self.add_30(conv2d_76_conv2d1, add_29);
    batch_normalization_63_fused_batch_norm = getattr(self, "batch_normalization_63/FusedBatchNorm")(add_30,
                                                                                                     self.initializers.onnx_initializer_61);
    batch_normalization_63_fused_batch_norm1 = getattr(self, "batch_normalization_63/FusedBatchNorm1")(
        batch_normalization_63_fused_batch_norm, self.initializers.onnx_initializer_62);
    leaky_relu_62_maximum_leaky_relu_62_mul = getattr(self, "LeakyRelu_62/Maximum;LeakyRelu_62/mul")(
        batch_normalization_63_fused_batch_norm1);
    batch_normalization_64_fused_batch_norm_conv2d_77_conv2d = getattr(self,
                                                                       "batch_normalization_64/FusedBatchNorm;conv2d_77/Conv2D")(
        leaky_relu_62_maximum_leaky_relu_62_mul);
    leaky_relu_63_maximum_leaky_relu_63_mul = getattr(self, "LeakyRelu_63/Maximum;LeakyRelu_63/mul")(
        batch_normalization_64_fused_batch_norm_conv2d_77_conv2d);
    conv2d_78_conv2d1 = getattr(self, "conv2d_78/Conv2D1")(leaky_relu_63_maximum_leaky_relu_63_mul);
    add_31 = self.add_31(conv2d_78_conv2d1, add_30);
    conv2d_79_bias_add_conv2d_79_conv2d_conv2d_78_bias_read = getattr(self,
                                                                      "conv2d_79/BiasAdd;conv2d_79/Conv2D;conv2d_78/bias/read")(
        add_31);
    transpose__1500 = self.Transpose__1500(conv2d_79_bias_add_conv2d_79_conv2d_conv2d_78_bias_read);
    reshape = self.Reshape(transpose__1500, self.initializers.onnx_initializer_63);
    shape = self.Shape(reshape);
    shape__870 = self.Shape__870(shape);
    softmax_tensor_0__874 = getattr(self, "softmax_tensor:0__874")(shape__870)
    slice_1 = self.Slice(shape__870, self.initializers.onnx_initializer_64, self.initializers.onnx_initializer_65);
    concat_6 = self.concat_6(self.initializers.onnx_initializer_66, slice_1);
    reshape_1_reshape__873 = getattr(self, "Reshape_1;Reshape__873")(concat_6);
    reshape_1_reshape = getattr(self, "Reshape_1;Reshape")(transpose__1500, reshape_1_reshape__873);
    softmax = self.Softmax(reshape_1_reshape);
    softmax_tensor_0 = getattr(self, "softmax_tensor:0")(softmax, softmax_tensor_0__874);
    return softmax_tensor_0


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
