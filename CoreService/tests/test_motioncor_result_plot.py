from pathlib import Path
import re


SHIFT_RE = re.compile(r"Add Frame #\d+ with xy shift: (-?\d+\.\d+) (-?\d+\.\d+)")


def parse_motioncor_shifts(log_path: Path) -> list[tuple[float, float]]:
    shifts = []
    with log_path.open() as f:
        for line in f:
            match = SHIFT_RE.search(line)
            if match:
                x, y = match.groups()
                shifts.append((float(x), float(y)))
    return shifts


def test_parse_motioncor_shifts_fixture():
    fixture = Path(__file__).with_name(
        "23mar23b_a_00038gr_00003sq_v02_00008hl_v01_00002ex_st_Log.txt"
    )

    shifts = parse_motioncor_shifts(fixture)

    assert shifts
    assert all(len(shift) == 2 for shift in shifts)
    assert shifts[0] == (-1.165, 1.195)
