"""
Standalone template picker for cryo-EM.

This package is independent of Appion/Leginon internals and exposes
an atomic API for template-based particle detection.
"""

from .picker import pick_particles

__all__ = ["pick_particles"]
