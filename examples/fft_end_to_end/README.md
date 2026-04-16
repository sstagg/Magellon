# FFT plugin end-to-end demo

A self-contained script that exercises the full bus-driven task flow
for the FFT plugin **without RabbitMQ, without docker, in one process**.

## What it shows

The script plays both sides of the bus:

- **CoreService side (main thread):** downloads 10 images, wraps each
  in a `TaskDto` + CloudEvents envelope, calls `bus.tasks.send(...)`.
- **Plugin side (background thread):** `FftBrokerRunner` registers
  as a consumer on the bus, decodes each delivery, runs
  `FftPlugin.execute`, and publishes the `TaskResultDto` back on the
  result route.

The bus is an `InMemoryBinder` — broker-shaped but pure Python, no
network I/O. It's the same binder used by SDK integration tests; the
demo is a worked example of the pattern.

The only thing different about a real production run: `install_rmq_bus`
instead of `install_inmemory_bus` at startup. Nothing else on the
plugin or dispatch side changes.

## Run

```
cd examples/fft_end_to_end
python run_demo.py                 # 10 images, downloads from picsum.photos
python run_demo.py --offline       # skip network, synthesize images
python run_demo.py --count 20      # different sample size
python run_demo.py -v              # verbose logging
```

First run creates `sample_images/` (the inputs) and `outputs/` (the
FFT PNGs). Both are gitignored. Subsequent runs reuse cached inputs.

## Requirements

- Python 3.12+
- The FFT plugin's deps installed (`pip install -r plugins/magellon_fft_plugin/requirements.txt`)
- The SDK installed in dev mode (`pip install -e magellon-sdk`)
- Internet for the download path (or pass `--offline`)

## Expected output

```
[1/4] acquiring 10 images → .../sample_images
       got 10 image(s)
[2/4] installing in-memory bus
[3/4] starting FFT plugin runner (consume=demo.fft.tasks)
[4/4] dispatching 10 FFT tasks
       waiting for drain (timeout=60.0s)

========================================================================
FFT demo — dispatched 10 tasks, received 10 results
========================================================================
  [ 1] 9a17...  code=200  msg='FFT successfully executed'
       → .../outputs/sample_00_FFT.png
  [ 2] b340...  code=200  msg='FFT successfully executed'
       → .../outputs/sample_01_FFT.png
  ...
```

Each `*_FFT.png` under `outputs/` is the log-magnitude 2D FFT of the
corresponding input image, rendered in grayscale.

## Adapting for your own images

Drop PNG / TIFF / MRC files into `sample_images/` with names matching
`sample_NN.{ext}` and the demo will use them instead of downloading.

## Why this example matters

- **No RMQ for local dev.** Before the `InMemoryBinder` shipped,
  exercising the runner end-to-end required docker-compose. Now it's
  a single `python` invocation.
- **MB4.2 smoke test.** Validates that `install_rmq_bus` swaps
  cleanly for `install_inmemory_bus` in plugin startup — the cleaner
  bootstrap contract introduced in MB4.1/MB4.2.
- **Plugin-author blueprint.** Copy-paste this to smoke-test a new
  plugin against the bus without the broker plumbing in the loop.
