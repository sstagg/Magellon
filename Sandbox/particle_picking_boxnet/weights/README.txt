BoxNet pretrained weights go here.

The Warp pretrained models live at:
  http://boxnet.warpem.com/models

The repo source is:
  https://github.com/cramerlab/boxnet

Drop the .pt file here as `boxnet.pt`. The same file used by the
Cianfrocco-lab `eval_micrograph` repo works (graph-trace PyTorch
conversion of the Warp BoxNet v2 TF model).

For the ONNX runtime path, run:
  python export_onnx.py
which writes weights/boxnet.onnx alongside the .pt.
