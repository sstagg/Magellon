MeasureIce HDF5 LUTs (one per microscope configuration).

Current contents
================

Krios_300kV.h5
    Generated 2026-05-13 by running upstream MeasureIce's
    Generate_MeasureIce_calibration.py with their bundled
    supercooled_water.xyz atomic model. Settings:

        keV          = 300
        apertures    = 5, 10, 15, 20 mrad
                       (labelled 50, 70, 100, 140 um for operator clarity)
        thickness    = 0 to 1500 nm in 50 nm steps
        atomic model = supercooled_water.xyz from
                       github.com/HamishGBrown/MeasureIce

    ALS coefficients (lambda, nm) from the simulation:
        5 mrad   ->  447
        10 mrad  ->  647
        15 mrad  ->  858     <- default for measure_thickness.py
        20 mrad  -> 1092

    Note: the lambda values above are computed from the full 0-1500 nm
    curve. They are slightly different (~10%) from the values reported
    by the upstream generator's stdout (396, 588, 799, 1049 nm), which
    were fit on a 0-600 nm curve. Beer-Lambert is only approximate at
    large thicknesses; the LUT itself is what the sandbox uses, not
    the scalar lambda.

Krios_300kV.pdf
    Reference plot of (thickness vs I/I_0) for all four apertures,
    produced by --Plot during LUT generation.

Regenerating
============

    pip install h5py numpy scipy matplotlib torch tqdm ase pypng hankel
    git clone https://github.com/HamishGBrown/MeasureIce.git
    git clone https://github.com/HamishGBrown/py_multislice.git
    pip install ./py_multislice ./MeasureIce
    cd MeasureIce
    # patch np.math.factorial -> math.factorial (NumPy 2 compat)
    python Generate_MeasureIce_calibration.py \
        -E 300 -A 5,10,15,20 -u mrad -m 50,70,100,140 \
        -o ../path/to/sandbox/luts/Krios_300kV.h5 -M Krios_300kV --Plot

For 200 kV or other microscopes, re-run with the appropriate -E and
the actual aperture half-angles (in mrad) for your scope.
