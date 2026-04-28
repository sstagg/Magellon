from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Blob:
    center: tuple[float, float]
    size: int
    mean: float
    stddev: float
    roundness: float
    maximum_position: tuple[int, int]
    label_index: int


@dataclass
class Hole:
    center: tuple[float, float]
    hole_number: int
    stats: dict[str, Any] = field(default_factory=dict)
    info: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.stats.setdefault("center", self.center)
        self.stats.setdefault("hole_number", self.hole_number)
        self.info.setdefault("center", self.center)


@dataclass
class LatticeFitResult:
    lattice: Any
    holes: list[Hole]
