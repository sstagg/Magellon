Drop high-magnitude cryo-EM MRC micrographs here (typical pixel size 0.5-2.0 A/px).

run_benchmarks.py will process every .mrc it finds in this folder.

Two staging paths are supported:

  1. Reuse the topaz sandbox's tutorial MRC:
       cp ../../particle_picking_topaz/example_images/*.mrc .

  2. Convert eval_micrograph's labelled PNG fixtures (great / bad / empty)
     into MRC format for a known-good vs known-bad reference pair:
       python convert_eval_images.py

  3. Bring an EMPIAR test image. EMPIAR-10017 was the BoxNet training
     reference; EMPIAR-10061 (apoferritin) is the Warp benchmark.
