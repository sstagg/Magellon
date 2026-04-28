# magellon-topaz-plugin

Magellon plugin for cryo-EM particle picking + denoising via [tbepler/topaz](https://github.com/tbepler/topaz) (GPL-3.0). Vendors topaz's preprocess/NMS/tile-stitch internals under GPL terms; runs three pretrained networks via `onnxruntime`, no PyTorch.

## Categories

Serves two `TaskCategory` slots from one container:

| Category | Code | Input (MRC) | Output |
|---|---:|---|---|
| `TopazParticlePicking` | 8 | High-mag (~0.5–2 Å/px) | Ranked particles + score + radius |
| `MicrographDenoising` | 9 | High-mag (~0.5–2 Å/px) | Denoised MRC + intensity stats |

Coordinate convention for picks: original-image pixel space (already up-scaled from the preprocessed grid the model runs on).

## Engine knobs (per-task `engine_opts`)

| field | category | default | notes |
|---|---|---|---|
| `model` | pick | `resnet16` | also `resnet8` |
| `radius` | pick | 14 | NMS radius in preprocessed pixels |
| `threshold` | pick | -3.0 | log-likelihood cutoff |
| `scale` | pick | 8 | preprocess downsample factor |
| `model` | denoise | `unet` | only `unet_l2` shipped |
| `patch_size` | denoise | 1024 | tile size for stitched inference |
| `padding` | denoise | 128 | overlap absorbed at tile edges |

## Runtime

- **No PyTorch, no topaz-em.** Three ONNX files (resnet16, resnet8, unet_L2) total ~17 MB shipped.
- **Pure numpy/scipy** for everything else: GMM-normalize, FFT downsample, NMS, denoise tile-stitch.
- **BatchNorm-free**: topaz detectors don't use BN, so the upstream `.eval()` quirk that caught us with ptolemy doesn't apply here.

## License

`plugin/topaz_lib/` is direct port of upstream topaz (GPL-3.0) numpy code. Three ONNX weight files were exported from upstream's bundled `.sav` checkpoints. Both stay under GPL-3.0; the rest of this plugin follows the Magellon repo license.
