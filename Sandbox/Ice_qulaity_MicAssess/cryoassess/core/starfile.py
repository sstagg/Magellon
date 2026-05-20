"""RELION star-file <-> pandas conversion.

A parsed star file is represented as a dict mapping each block code
(``"data_..."``) to a list of :class:`pandas.DataFrame`, one per ``loop_``
block.  Every cell is kept as a string, matching RELION's untyped layout.
Comment lines (starting with ``#``) are dropped during parsing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Union

import pandas as pd

StarDataFrames = Dict[str, List[pd.DataFrame]]
PathLike = Union[str, Path]


def _loop_to_df(loop: List[str]) -> pd.DataFrame:
    """Convert one ``loop_`` block (its lines) into a DataFrame."""

    key_indices = [i for i, line in enumerate(loop) if line.startswith("_")]
    # A key line may carry a trailing "#3" column index -- strip it.
    columns = [loop[i].split("#", 1)[0].strip() for i in key_indices]

    rows = [line.split() for line in loop[key_indices[-1] + 1:]]
    df = pd.DataFrame(rows).dropna()
    df.columns = columns
    return df


def _block_to_dfs(block: List[str]) -> List[pd.DataFrame]:
    """Split a block into its ``loop_`` sections and convert each to a DataFrame."""

    loop_starts = [i for i, line in enumerate(block) if line == "loop_"]
    loop_starts.append(len(block))
    return [
        _loop_to_df(block[loop_starts[i]:loop_starts[i + 1]])
        for i in range(len(loop_starts) - 1)
    ]


def read_star(path: PathLike) -> StarDataFrames:
    """Parse a star file into ``{blockcode: [DataFrame, ...]}``."""

    with open(path) as handle:
        lines = [
            stripped
            for stripped in (line.strip() for line in handle)
            if stripped and not stripped.startswith("#")
        ]

    block_starts = [i for i, line in enumerate(lines) if line.startswith("data_")]
    block_codes = [lines[i] for i in block_starts]
    block_starts.append(len(lines))
    blocks = [
        lines[block_starts[i]:block_starts[i + 1]]
        for i in range(len(block_starts) - 1)
    ]
    return dict(zip(block_codes, (_block_to_dfs(block) for block in blocks)))


def _write_loop(df: pd.DataFrame, handle) -> None:
    handle.write("loop_ \n")
    for column in df.columns.tolist():
        handle.write(column + " \n")
    for i in range(len(df)):
        handle.write("  ".join(df.iloc[i].tolist()) + " \n")
    handle.write("\n")


def write_star(star_df: StarDataFrames, path: PathLike) -> None:
    """Write a parsed star structure back out to ``path``."""

    with open(path, "w") as handle:
        for block_code, df_list in star_df.items():
            handle.write(block_code + " \n\n")
            for df in df_list:
                _write_loop(df, handle)


def micrograph_blockcode(star_df: StarDataFrames) -> str:
    """Return the block code that holds the micrograph table.

    A single-block file uses that block; a multi-block (RELION 3.1) file uses
    the conventional ``data_micrographs`` block.
    """

    codes = list(star_df.keys())
    return codes[0] if len(codes) == 1 else "data_micrographs"


def star_to_micrograph_list(path: PathLike) -> List[str]:
    """Return the ``_rlnMicrographName`` column from a star file."""

    star_df = read_star(path)
    block = micrograph_blockcode(star_df)
    return star_df[block][0]["_rlnMicrographName"].tolist()
