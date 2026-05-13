Drop cryo-EM MRC files here for measure_thickness.py / analyze_dir.py.

Two staging paths recommended:

  1. Reuse the 24dec03a atlas dataset already on your data plane:
       cp /c/magellon/gpfs/24dec03a/home/original/*.mrc .
     (Atlas level; gives RELATIVE thickness; see README.md caveats.)

  2. For a true MeasureIce validation, drop in medium-mag hole imagery
     (~50-500 A/px) where both ice and a clean vacuum region (the hole
     bowl) are visible in the same frame.

For absolute, microscope-calibrated thickness, also need:
  - The microscope's HDF5 LUT under ../luts/, OR
  - --t-eff <nm> appropriate for the kV + objective aperture (see README).
