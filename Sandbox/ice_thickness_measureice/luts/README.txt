MeasureIce HDF5 LUTs (one per microscope configuration) go here.

The upstream MeasureIce project ships pre-simulated LUTs for the common
Krios / Glacios configurations. URL:
  https://github.com/HamishGBrown/MeasureIce

A LUT is a 1-D table indexed by intensity ratio (I/I_0) returning
ice thickness in nm. For sandbox purposes we currently approximate
with a single scalar T_eff (see measure_thickness.py:DEFAULT_T_EFF_NM
and the T_EFF_PRESETS dict). Drop a real LUT here and a future
revision of measure_thickness.py can swap it in via scipy.interpolate.

No LUT file is committed — they're per-microscope and small enough to
re-download as needed.
