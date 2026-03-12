# Cryo-EM Projection Tool

This package provides CPU-only cryo-EM projection tooling with:

- A reusable Python backend for MRC I/O and projection generation.
- A CLI for offline projection jobs.
- A GUI with RELION-style Euler sliders for interactive inspection and saving.

## Install

```bash
pip install -r requirements.txt
```

## CLI

- Start interactive GUI:

```bash
python main.py gui --input map.mrc
```

- Render a stack using explicit Euler angles:

```bash
python main.py project --input map.mrc --output out_stack.mrc \
  --euler 0 90 0 --euler 45 30 180
```

- Render the same with the FFT reference backend:

```bash
python main.py project --input map.mrc --output out_stack_fft.mrc --backend fft-reference \
  --euler 0 90 0 --euler 45 30 180
```

- Render a stack using even sampling:

```bash
python main.py project --input map.mrc --sample-n 120 --output out_stack.mrc
```

- Scale down on load for faster interactive updates:

```bash
python main.py gui --input map.mrc --scale 0.5
python main.py project --input map.mrc --sample-n 120 --scale 0.5 --output out_stack.mrc
```

### GUI backend

- GUI default is real-space (stable default).
- You can switch to `fft-reference` in the GUI backend controls.

## GUI behavior

- Sliders:
  - `rot` in `[-180, 180]`
  - `tilt` in `[0, 180]`
  - `psi` in `[-180, 180]`
- “Save current projection (MRC)” writes a single 2D MRC at the current angles.
- CLI `project`/`sample` always writes an MRC stack with shape `(N, Y, X)`.
