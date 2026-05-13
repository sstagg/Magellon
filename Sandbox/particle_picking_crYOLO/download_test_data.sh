#!/usr/bin/env bash
# Downloads the crYOLO TcdA1 reference bundle (toxin_reference.zip).
#
# NOTE: ~1.96 GB. Has full training MRCs + reference picks + reference model.
# After download, unpacks training MRCs into example_images/, ground-truth
# box files into example_images/box_ground_truth/, and the reference .h5
# into weights/.

set -euo pipefail

URL="https://owncloud.gwdg.de/index.php/s/SjzATaIMZaANrnm/download"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZIP_PATH="$SCRIPT_DIR/toxin_reference.zip"
STAGE_DIR="$SCRIPT_DIR/toxin_reference"
EXAMPLES="$SCRIPT_DIR/example_images"
WEIGHTS="$SCRIPT_DIR/weights"

if [[ ! -f "$ZIP_PATH" ]]; then
  echo "Downloading $URL"
  echo "  -> $ZIP_PATH  (~1.96 GB — be patient)"
  curl -L --fail -o "$ZIP_PATH" "$URL"
else
  echo "Already downloaded: $ZIP_PATH"
fi

if [[ ! -d "$STAGE_DIR" ]]; then
  echo "Unzipping ..."
  unzip -q "$ZIP_PATH" -d "$STAGE_DIR"
else
  echo "Already unzipped: $STAGE_DIR"
fi

shopt -s globstar nullglob
TRAIN_MRC=( "$STAGE_DIR"/**/*.mrc )
BOX_FILES=( "$STAGE_DIR"/**/*.box )
REF_MODELS=( "$STAGE_DIR"/**/*.h5 )

if (( ${#TRAIN_MRC[@]} > 0 )); then
  cp -f "${TRAIN_MRC[@]}" "$EXAMPLES/"
  echo "Copied ${#TRAIN_MRC[@]} training MRCs into $EXAMPLES"
fi
if (( ${#BOX_FILES[@]} > 0 )); then
  mkdir -p "$EXAMPLES/box_ground_truth"
  cp -f "${BOX_FILES[@]}" "$EXAMPLES/box_ground_truth/"
  echo "Copied ${#BOX_FILES[@]} ground-truth box files into $EXAMPLES/box_ground_truth"
fi
if (( ${#REF_MODELS[@]} > 0 )); then
  cp -f "${REF_MODELS[0]}" "$WEIGHTS/"
  echo "Copied reference model: $(basename "${REF_MODELS[0]}") -> $WEIGHTS"
fi

echo
echo "Done. Next:"
echo "  python pick_algorithm.py example_images/<one of the training mrcs>"
