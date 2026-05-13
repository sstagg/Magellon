crYOLO general pretrained models go here. Two sources:

  - SPHIRE general model (PhosaurusNet, .h5):
      https://cryolo.readthedocs.io/en/stable/installation.html
        gmodel_phosnet_*.h5   (drop into this folder)

  - The TcdA1 tutorial bundle ships a reference_model.h5 inside
    toxin_reference.zip. ./download_test_data.sh stages it here.

Once an ONNX export of the general model is verified (see export_onnx.py),
a corresponding cryolo_general.onnx can also live in this folder for the
runtime-light plugin path.
