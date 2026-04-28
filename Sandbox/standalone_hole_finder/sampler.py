from __future__ import annotations

import math
import random

import models

Hole = models.Hole


def _calculate_even_distribution(total: int, n_class: int) -> list[tuple[int, int]]:
    sampling_order = list(range(n_class)) * int(math.floor(total / float(n_class)))
    if len(sampling_order) < total:
        sampling_order.extend(random.sample(range(n_class), total - len(sampling_order)))
    nsample_in_classes = [sampling_order.count(index) for index in range(n_class)]
    last = 0
    ranges: list[tuple[int, int]] = []
    for count in nsample_in_classes:
        start = last
        end = start + count
        ranges.append((start, end))
        last = end
    return ranges


def sample_holes(
    holes: list[Hole],
    classes: int = 1,
    samples: int = -1,
    category: str = "center",
) -> list[Hole]:
    if not holes:
        return holes
    if samples == 0:
        return []
    if samples == -1 or samples >= len(holes):
        return holes
    if category not in holes[0].stats:
        raise ValueError(f'category "{category}" not found in hole stats')

    sorted_holes = sorted(holes, key=lambda hole: hole.stats[category], reverse=True)
    range_list = _calculate_even_distribution(len(sorted_holes), classes)
    bins = [sorted_holes[start:end] for start, end in range_list]

    selected: list[Hole] = []
    if classes == 2 and samples == 2 and bins[0] and bins[1]:
        selected.append(bins[0][0])
        selected.append(bins[1][-1])
    else:
        sampling_order = list(range(classes)) * int(math.ceil(samples / float(classes)))
        sampling_order = sampling_order[:samples]
        for index in sampling_order:
            if not bins[index]:
                continue
            pick = random.sample(range(len(bins[index])), 1)[0]
            selected.append(bins[index].pop(pick))
    return sorted(selected, key=lambda hole: hole.stats[category])
