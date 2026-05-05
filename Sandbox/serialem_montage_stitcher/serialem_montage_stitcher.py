#!/usr/bin/env python
"""Stitch montage images from a SerialEM medium_mag import."""

import argparse
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import mrcfile
import numpy as np

mont_block_re = re.compile(r'\[MontSection\s*=\s*(\d+)\](.*?)(?=\[MontSection|\Z)', re.DOTALL)
zval_re = re.compile(
    r'\[ZValue\s*=\s*(\d+)\].*?'
    r'PieceCoordinates\s*=\s*([-0-9.eE]+)\s+([-0-9.eE]+).*?'
    r'NavigatorLabel\s*=\s*(\S+).*?'
    r'(?:AlignedPieceCoords\s*=\s*([-0-9.eE]+)\s+([-0-9.eE]+).*?)?'
    r'(?:XedgeDxyVS\s*=\s*([-0-9.eE]+)\s+([-0-9.eE]+).*?)?'
    r'(?:YedgeDxyVS\s*=\s*([-0-9.eE]+)\s+([-0-9.eE]+))?',
    re.DOTALL,
)


def parse_mmm_mdoc(mdoc_text: str) -> Tuple[List[List[Dict]], set]:
    """Parse a SerialEM montage .mdoc text and return montage groups."""
    montages = []
    navigator_labels = set()

    for mont_match in mont_block_re.finditer(mdoc_text):
        block = mont_match.group(2)
        coords_list = []

        for z_match in zval_re.finditer(block):
            z_idx = int(z_match.group(1))
            piece_x, piece_y = float(z_match.group(2)), float(z_match.group(3))
            navigator_label = z_match.group(4)
            navigator_labels.add(navigator_label)

            if z_match.group(5) and z_match.group(6):
                aligned_x, aligned_y = float(z_match.group(5)), float(z_match.group(6))
            else:
                aligned_x, aligned_y = piece_x, piece_y

            coords_list.append({
                'ZValue': z_idx,
                'NavigatorLabel': navigator_label,
                'PieceCoordinates': (piece_x, piece_y),
                'AlignedPieceCoords': (aligned_x, aligned_y),
                'sequence': z_idx,
            })

        coords_list.sort(key=lambda d: d['ZValue'])
        for i in range(0, len(coords_list), 24):
            group = coords_list[i:i + 24]
            if group:
                montages.append(group)

    return montages, navigator_labels


def stitch_mmm(pieces: List[Dict], mrc_path: Path, option: str = "AlignedPieceCoords") -> Tuple[np.ndarray, List[Tuple[float, float]], List[List[float]]]:
    """Stitch a montage from pieces and the corresponding medium_mag .mrc file."""
    if option not in ("PieceCoordinates", "AlignedPieceCoords", "AlignedPieceCoordsVS"):
        raise ValueError(f"Unknown option: {option}")

    with mrcfile.mmap(str(mrc_path), permissive=True) as mrc:
        slices = [mrc.data[piece['sequence']] for piece in pieces]

    coords = []
    for piece in pieces:
        if option not in piece:
            x, y = piece["PieceCoordinates"][1], piece["PieceCoordinates"][0]
        else:
            x, y = piece[option][1], piece[option][0]
            if x < -1_000_000_000 or y < -1_000_000_000:
                x, y = piece["PieceCoordinates"][1], piece["PieceCoordinates"][0]
        coords.append((x, y))

    piece_stageXYs = [piece.get('StagePosition', (0, 0)) for piece in pieces]
    shapes = [slice_data.shape for slice_data in slices]

    min_y = min(y for (y, x) in coords)
    min_x = min(x for (y, x) in coords)
    offset_y = -min_y if min_y < 0 else 0
    offset_x = -min_x if min_x < 0 else 0

    max_y = max(y + shape[0] for (y, x), shape in zip(coords, shapes))
    max_x = max(x + shape[1] for (y, x), shape in zip(coords, shapes))
    montage_shape = (int(offset_y + max_y), int(offset_x + max_x))

    montage = np.zeros(montage_shape, dtype=np.int16)
    piece_center_coords = []

    for slice_data, (y, x) in zip(slices, coords):
        h, w = slice_data.shape
        y_off, x_off = y + offset_y, x + offset_x
        montage[int(y_off):int(y_off) + int(h), int(x_off):int(x_off) + int(w)] = slice_data
        piece_center_coords.append([x_off + w / 2, y_off + h / 2])

    return montage, piece_stageXYs, piece_center_coords


def find_mrc_mdoc_pairs(medium_mag_dir: Path) -> List[Dict[str, str]]:
    """Find medium_mag .mrc / .mrc.mdoc pairs in a SerialEM medium_mag folder."""
    if not medium_mag_dir.exists() or not medium_mag_dir.is_dir():
        raise FileNotFoundError(f"Directory not found: {medium_mag_dir}")

    files = [p.name for p in medium_mag_dir.iterdir() if p.is_file()]
    mrc_files = [f for f in files if f.endswith('.mrc')]
    pairs = []

    for mrc in mrc_files:
        mdoc = f"{mrc}.mdoc"
        mrc_path = medium_mag_dir / mrc
        mdoc_path = medium_mag_dir / mdoc
        if mdoc_path.exists():
            pairs.append({'mrc': str(mrc_path), 'mdoc': str(mdoc_path)})

    return pairs


def save_montage(output_path: Path, montage: np.ndarray) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with mrcfile.new(str(output_path), overwrite=True) as mrc:
        mrc.set_data(montage.astype(np.float32))


def stitch_medium_mag(medium_mag_dir: Path, output_dir: Path, option: str) -> List[str]:
    pairs = find_mrc_mdoc_pairs(medium_mag_dir)
    if not pairs:
        raise FileNotFoundError(f"No .mrc / .mrc.mdoc pairs found in {medium_mag_dir}")

    saved_paths = []
    for pair in pairs:
        mrc_path = Path(pair['mrc'])
        mdoc_path = Path(pair['mdoc'])
        with mdoc_path.open('r', encoding='utf-8', errors='ignore') as f:
            mdoc_text = f.read()

        montages, navigator_labels = parse_mmm_mdoc(mdoc_text)
        pair_name = mrc_path.stem

        for idx, pieces in enumerate(montages):
            montage, stage_positions, centers = stitch_mmm(pieces, mrc_path, option=option)
            label = pieces[0].get('NavigatorLabel', f'montage{idx}')
            filename = output_dir / f"{pair_name}_{label}.mrc"
            save_montage(filename, montage)
            saved_paths.append(str(filename.resolve()))

    return saved_paths


def parse_args():
    parser = argparse.ArgumentParser(
        description='Stitch SerialEM medium_mag montage images from a SerialEM import folder.'
    )
    parser.add_argument('--medium-dir', type=Path, required=True,
                        help='Path to the SerialEM medium_mag directory')
    parser.add_argument('--output-dir', type=Path, default=Path('stitched_montages'),
                        help='Directory to write stitched montage MRC files')
    parser.add_argument('--option', choices=['PieceCoordinates', 'AlignedPieceCoords', 'AlignedPieceCoordsVS'],
                        default='AlignedPieceCoords',
                        help='Piece coordinate option to use for stitching')
    return parser.parse_args()


def main():
    args = parse_args()
    output_dir = args.output_dir
    montage_paths = stitch_medium_mag(args.medium_dir, output_dir, args.option)

    print(f'Stitched {len(montage_paths)} montage(s) from {args.medium_dir}')
    for path in montage_paths:
        print(path)


if __name__ == '__main__':
    main()
