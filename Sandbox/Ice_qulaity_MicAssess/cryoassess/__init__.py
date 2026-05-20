"""cryoassess -- automated cryo-EM micrograph and 2D class-average quality assessment.

Layered structure:

* :mod:`cryoassess.core`   -- pure, TensorFlow-free numerical routines (testable).
* :mod:`cryoassess.models` -- TensorFlow model construction and inference.
* :mod:`cryoassess.cli`    -- ``micassess`` / ``2dassess`` command-line entry points.
"""

__version__ = "2.0.0"
