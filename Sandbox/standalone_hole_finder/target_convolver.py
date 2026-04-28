from __future__ import annotations

import models

Hole = models.Hole


def make_convolved_targets(
    holes: list[Hole],
    conv_vect: list[tuple[float, float]] | None,
    image_shape: tuple[int, int],
) -> list[Hole]:
    if not conv_vect:
        return []
    convolved: list[Hole] = []
    for hole in holes:
        for dr, dc in conv_vect:
            center = hole.stats["center"]
            target = (center[0] + dr, center[1] + dc)
            row = target[0]
            col = target[1]
            if col < 0 or col >= image_shape[1] or row < 0 or row >= image_shape[0]:
                continue
            info = dict(hole.info)
            info.update(hole.stats)
            info["center"] = target
            info["convolved"] = True
            convolved.append(Hole(center=target, hole_number=int(hole.stats["hole_number"]), stats=dict(info), info=info))
    return convolved
