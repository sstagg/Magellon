"""
Standalone stack maker for cryo-EM micrograph particle extraction.

This module is intentionally isolated from backend systems and exposes a
small atomic API that can be reused by a plugin wrapper.
"""

from .stack_maker import (
    CTFParams,
    ParticleCoordinate,
    ParticleStackConfig,
    ParticleStackRow,
    build_and_write,
    build_particle_records,
    create_particle_stack,
    write_json_output,
    write_relion_star,
)

__all__ = [
    "CTFParams",
    "ParticleCoordinate",
    "ParticleStackConfig",
    "ParticleStackRow",
    "build_and_write",
    "build_particle_records",
    "create_particle_stack",
    "write_json_output",
    "write_relion_star",
]
