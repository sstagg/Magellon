#!/usr/bin/env python
"""Generate SVG tile-pattern diagrams from SerialEM montage .mdoc files.

This does not read the MRC image data. It draws labeled rectangles from the
metadata coordinates so the acquisition order and tile locations are visible.
"""

import argparse
import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


COORD_OPTIONS = ("PieceCoordinates", "AlignedPieceCoords", "AlignedPieceCoordsVS")
Z_BLOCK_RE = re.compile(r"\[ZValue\s*=\s*(\d+)\](.*?)(?=\n\[ZValue\s*=|\n\[MontSection\s*=|\Z)", re.DOTALL)
NUMBER_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
MISSING_COORD_LIMIT = -1_000_000_000


@dataclass
class Piece:
    zvalue: int
    sequence: int
    coords: Dict[str, Tuple[float, float]]
    navigator_label: Optional[str]


@dataclass
class MdocPattern:
    mdoc_path: Path
    image_size: Tuple[float, float]
    full_mont_frames: Optional[Tuple[int, int]]
    pieces: List[Piece]


def parse_number_pair(value: str) -> Optional[Tuple[float, float]]:
    numbers = NUMBER_RE.findall(value)
    if len(numbers) < 2:
        return None
    return float(numbers[0]), float(numbers[1])


def parse_key_values(text: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for raw_line in text.splitlines():
        if "=" not in raw_line or raw_line.lstrip().startswith("["):
            continue
        key, value = raw_line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def parse_mdoc(mdoc_path: Path, tile_size: Optional[Tuple[float, float]] = None) -> MdocPattern:
    text = mdoc_path.read_text(encoding="utf-8", errors="ignore")
    top_values = parse_key_values(text)

    image_size = tile_size or parse_number_pair(top_values.get("ImageSize", ""))
    if image_size is None:
        raise ValueError(f"{mdoc_path} has no ImageSize; pass --tile-size WIDTHxHEIGHT")

    full_mont_frames_pair = parse_number_pair(top_values.get("FullMontNumFrames", ""))
    full_mont_frames = None
    if full_mont_frames_pair is not None:
        full_mont_frames = int(full_mont_frames_pair[0]), int(full_mont_frames_pair[1])

    pieces: List[Piece] = []
    for sequence, match in enumerate(Z_BLOCK_RE.finditer(text)):
        zvalue = int(match.group(1))
        block_values = parse_key_values(match.group(2))
        coords: Dict[str, Tuple[float, float]] = {}
        for option in COORD_OPTIONS:
            coord_pair = parse_number_pair(block_values.get(option, ""))
            if coord_pair is not None:
                coords[option] = coord_pair

        if "PieceCoordinates" not in coords:
            continue

        pieces.append(
            Piece(
                zvalue=zvalue,
                sequence=sequence,
                coords=coords,
                navigator_label=block_values.get("NavigatorLabel"),
            )
        )

    if not pieces:
        raise ValueError(f"No ZValue blocks with PieceCoordinates found in {mdoc_path}")

    return MdocPattern(
        mdoc_path=mdoc_path,
        image_size=image_size,
        full_mont_frames=full_mont_frames,
        pieces=pieces,
    )


def find_mdoc_files(medium_dir: Path) -> List[Path]:
    if not medium_dir.exists() or not medium_dir.is_dir():
        raise FileNotFoundError(f"Directory not found: {medium_dir}")
    return sorted(path for path in medium_dir.iterdir() if path.is_file() and path.name.endswith(".mrc.mdoc"))


def selected_coord(piece: Piece, option: str) -> Tuple[float, float]:
    coord = piece.coords.get(option) or piece.coords["PieceCoordinates"]
    if coord[0] < MISSING_COORD_LIMIT or coord[1] < MISSING_COORD_LIMIT:
        return piece.coords["PieceCoordinates"]
    return coord


def ranked_locations(pieces: Iterable[Piece]) -> Dict[int, Tuple[int, int]]:
    raw_coords = {piece.zvalue: piece.coords["PieceCoordinates"] for piece in pieces}
    xs = sorted({coord[0] for coord in raw_coords.values()})
    ys = sorted({coord[1] for coord in raw_coords.values()})
    x_rank = {x: index + 1 for index, x in enumerate(xs)}
    y_rank = {y: index + 1 for index, y in enumerate(ys)}
    return {zvalue: (x_rank[x], y_rank[y]) for zvalue, (x, y) in raw_coords.items()}


def label_for(piece: Piece, label_mode: str, locations: Dict[int, Tuple[int, int]]) -> Tuple[str, str]:
    col, row = locations[piece.zvalue]
    if label_mode == "index":
        return str(piece.sequence), f"row {row}, col {col}"
    if label_mode == "grid":
        return f"{row},{col}", f"Z {piece.zvalue}"
    if label_mode == "both":
        return f"Z{piece.zvalue}", f"row {row}, col {col}"
    return str(piece.zvalue), f"row {row}, col {col}"


def svg_text(x: float, y: float, text: str, size: float, weight: str = "400", anchor: str = "middle") -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" '
        f'font-size="{size:.2f}" font-weight="{weight}">{html.escape(text)}</text>'
    )


def render_svg(pattern: MdocPattern, option: str, label_mode: str, max_width: int, max_height: int) -> str:
    tile_width, tile_height = pattern.image_size
    placements = []
    for piece in pattern.pieces:
        x, y = selected_coord(piece, option)
        placements.append((piece, x, y))

    min_x = min(x for _, x, _ in placements)
    min_y = min(y for _, _, y in placements)
    max_x = max(x + tile_width for _, x, _ in placements)
    max_y = max(y + tile_height for _, _, y in placements)
    montage_width = max_x - min_x
    montage_height = max_y - min_y

    diagram_top = 72.0
    margin = 24.0
    scale = min(max_width / montage_width, max_height / montage_height)
    scale = max(scale, 0.01)
    canvas_width = montage_width * scale + margin * 2
    canvas_height = montage_height * scale + diagram_top + margin
    tile_w = tile_width * scale
    tile_h = tile_height * scale
    main_font = max(10.0, min(34.0, tile_h * 0.34, tile_w * 0.28))
    sub_font = max(7.0, min(14.0, tile_h * 0.11, tile_w * 0.10))
    locations = ranked_locations(pattern.pieces)

    frame_text = ""
    if pattern.full_mont_frames:
        frame_text = f" | frames {pattern.full_mont_frames[0]} x {pattern.full_mont_frames[1]}"

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width:.0f}" height="{canvas_height:.0f}" '
        f'viewBox="0 0 {canvas_width:.2f} {canvas_height:.2f}">',
        "<style>",
        "text { font-family: Arial, Helvetica, sans-serif; fill: #111827; }",
        ".tile { fill: #dbeafe; stroke: #1f2937; stroke-width: 1.25; }",
        ".tile:nth-of-type(2n) { fill: #dcfce7; }",
        ".tile:nth-of-type(3n) { fill: #fee2e2; }",
        ".tile:nth-of-type(5n) { fill: #fef3c7; }",
        ".subtitle { fill: #4b5563; }",
        "</style>",
        '<rect x="0" y="0" width="100%" height="100%" fill="#ffffff"/>',
        svg_text(margin, 28, pattern.mdoc_path.name, 18, "700", "start"),
        svg_text(margin, 52, f"{len(pattern.pieces)} tiles | {option}{frame_text}", 13, "400", "start"),
    ]

    for piece, raw_x, raw_y in sorted(placements, key=lambda item: item[0].zvalue):
        x = margin + (raw_x - min_x) * scale
        y = diagram_top + (raw_y - min_y) * scale
        center_x = x + tile_w / 2
        center_y = y + tile_h / 2
        primary, secondary = label_for(piece, label_mode, locations)
        col, row = locations[piece.zvalue]
        hover = (
            f"ZValue {piece.zvalue}; sequence {piece.sequence}; row {row}; col {col}; "
            f"{option} x={raw_x:g}, y={raw_y:g}"
        )
        if piece.navigator_label:
            hover += f"; NavigatorLabel {piece.navigator_label}"

        parts.extend(
            [
                f'<g class="tile-group">',
                f'<rect class="tile" x="{x:.2f}" y="{y:.2f}" width="{tile_w:.2f}" height="{tile_h:.2f}" rx="2" ry="2">'
                f'<title>{html.escape(hover)}</title></rect>',
                svg_text(center_x, center_y - sub_font * 0.2, primary, main_font, "700"),
                f'<text class="subtitle" x="{center_x:.2f}" y="{center_y + main_font * 0.72:.2f}" '
                f'text-anchor="middle" font-size="{sub_font:.2f}">{html.escape(secondary)}</text>',
                "</g>",
            ]
        )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def parse_tile_size(value: str) -> Tuple[float, float]:
    match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*[x,]\s*(\d+(?:\.\d+)?)\s*$", value)
    if not match:
        raise argparse.ArgumentTypeError("Expected WIDTHxHEIGHT, for example 2532x1996")
    return float(match.group(1)), float(match.group(2))


def output_name_for(mdoc_path: Path, option: str) -> str:
    stem = mdoc_path.name
    if stem.endswith(".mrc.mdoc"):
        stem = stem[:-9]
    else:
        stem = mdoc_path.stem
    return f"{stem}_{option}_pattern.svg"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate labeled SVG montage tile-pattern diagrams from SerialEM .mdoc metadata."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--medium-dir", type=Path, help="Folder containing .mrc.mdoc files")
    source.add_argument("--mdoc", type=Path, help="Single .mrc.mdoc file to render")
    parser.add_argument("--output-dir", type=Path, default=Path("montage_patterns"), help="Directory for SVG files")
    parser.add_argument("--option", choices=COORD_OPTIONS, default="PieceCoordinates", help="Coordinate field to draw")
    parser.add_argument("--label", choices=("zvalue", "index", "grid", "both"), default="zvalue", help="Tile label style")
    parser.add_argument("--tile-size", type=parse_tile_size, help="Override tile size as WIDTHxHEIGHT if ImageSize is missing")
    parser.add_argument("--max-width", type=int, default=1600, help="Maximum diagram area width before margins")
    parser.add_argument("--max-height", type=int, default=1400, help="Maximum diagram area height before title and margins")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mdoc_paths = [args.mdoc] if args.mdoc else find_mdoc_files(args.medium_dir)
    if not mdoc_paths:
        raise FileNotFoundError(f"No .mrc.mdoc files found in {args.medium_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    saved_paths = []
    for mdoc_path in mdoc_paths:
        pattern = parse_mdoc(mdoc_path, tile_size=args.tile_size)
        svg = render_svg(pattern, option=args.option, label_mode=args.label, max_width=args.max_width, max_height=args.max_height)
        output_path = args.output_dir / output_name_for(mdoc_path, args.option)
        output_path.write_text(svg, encoding="utf-8")
        saved_paths.append(output_path.resolve())

    print(f"Generated {len(saved_paths)} pattern SVG file(s)")
    for path in saved_paths:
        print(path)


if __name__ == "__main__":
    main()
