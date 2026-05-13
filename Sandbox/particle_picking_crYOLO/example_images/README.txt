Drop high-magnitude cryo-EM MRC micrographs here (typical pixel size 0.5-2.0 A/px).

run_benchmarks.py will process every .mrc it finds in this folder.

Two staging paths are supported:

  1. Reuse the topaz sandbox's tutorial MRC (already validated against
     the topaz picker):
       cp ../../particle_picking_topaz/example_images/*.mrc .

  2. Download the crYOLO TcdA1 reference bundle (~1.96 GB, includes
     ground-truth .box files and a pretrained reference_model.h5):
       ./download_test_data.sh     # or download_test_data.ps1 on Windows
