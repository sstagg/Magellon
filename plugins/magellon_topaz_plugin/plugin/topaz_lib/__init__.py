"""Vendored topaz internals — pure numpy/scipy, no torch.

Three modules:
  * preprocess.py — downsample + GMM normalize (mirror of ``topaz preprocess``)
  * nms.py        — non-maximum suppression on a score map
  * denoise_io.py — patch/stitch driver for the denoiser

Copied from upstream topaz (GPL-3.0) commit pinned in the sandbox export.
"""
