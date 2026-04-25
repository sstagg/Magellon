Topaz ships its pretrained picker (resnet16_u64, resnet8_u64, conv63, conv127) and
denoiser (unet, unet_small, fcnn, affine) inside the topaz-em pip package at
  <venv>/site-packages/topaz/pretrained/detector/*.sav
  <venv>/site-packages/topaz/pretrained/denoise/*.sav

Nothing needs to live in this folder by default.

If you want to use a custom-trained model, drop the .sav file here and pass the
full path via --model:
  python pick_algorithm.py micrograph.mrc --model weights/my_model.sav
