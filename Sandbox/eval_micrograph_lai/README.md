# Micrograph Evaluation

This repository evaluates micrograph images using a pretrained model and returns a single quality score.

## Input

- A grayscale or color image file
- Supported formats: PNG, JPG, JPEG
- Provide the file path via `--inputfile`

## Output

- Prints the evaluation score to standard output
- Example output: `0.8234`

## Setup

1. Create and activate the virtual environment:

```bash
cd /Users/puneethreddymotukurudamodar/Downloads/eval_micrograph
python3 -m venv .venv
source .venv/bin/activate
```

2. Install required packages:

```bash
python -m pip install -r requirements.txt
```

## Run

```bash
python micrograph_eval.py --inputfile "inputfile.png"
```

## Notes

- The model file `boxnet.pt` must be present in the repository root.
- The script converts the input image to grayscale before evaluation.
- A `requirements.txt` file is included with all needed dependencies.
