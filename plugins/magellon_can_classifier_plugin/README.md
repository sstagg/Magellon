# magellon_can_classifier_plugin

CAN 2D-classification plugin — runs competitive-Hebbian topology +
multi-reference alignment on a RELION particle stack, emits class
averages + assignments + FRC summaries. Phase 7 deliverable
(2026-05-03).

Category: `TWO_D_CLASSIFICATION` (code 4).
Backend id: `can-classifier`.
Subject: `particle_stack` (one task per stack — *not* per image, per
ratified rule 7).
Cardinality: **1 task per stack** — the classifier consumes an
aggregate, so it does NOT fan out N image-tasks like the pre-pipeline
plugins do.

## Status

**Phase 7 (scaffold)**: SDK contract + plugin shell + contract tests.
**Phase 7b (vendor)** *(2026-05-03)*: algorithm vendored from
`Sandbox/magellon_can_classifier/classifier.py` into
`plugin/algorithm/`. `compute.classify_stack` now does the full
orchestration: STAR parsing → per-particle MRC reads → preprocess →
align+CAN → output writing.

### What ships now

- 1714-line algorithm at `plugin/algorithm/classifier.py` (numpy +
  scipy + lazy torch / scikit-image / scikit-learn for the GPU paths).
- `plugin/compute.py` — STAR parser, RELION `NNNNNN@stack.mrcs` token
  resolver, output writers, and the public `classify_stack` entry
  point used by `plugin/plugin.py`.
- `requirements.txt` / `pyproject.toml` carry torch + scikit-image +
  scikit-learn pins.
- Dockerfile carries a runbook comment for switching the base to
  `nvidia/cuda:12.1-runtime` for production GPU deployments.
- 9 contract pin tests (mocked compute path stays valid; new tests
  pin the vendored algorithm subpackage exists with the right
  public API).

### What's still deferred

- **Production CUDA build.** The Dockerfile keeps `python:3.11-slim`
  so CI without a GPU can still build + run contract tests. Switch
  the FROM line + add `--extra-index-url https://download.pytorch.org/whl/cu121`
  to the pip install in deploys with a real GPU.
- **End-to-end integration test on a synthetic 20-particle stack**.
  Lands when the test environment has torch installed (CI runner
  swap or a dedicated GPU job).
- **Subject axis dispatch wiring**. The classifier reads paths
  directly from `TwoDClassificationInput.mrcs_path` / `.star_path`;
  Phase 3d's `TaskMessage.subject_id` is propagated through the
  result envelope but the dispatch HTTP endpoint that resolves a
  `particle_stack_id` artifact → input paths is still to-do.

See `Documentation/CATEGORIES_AND_BACKENDS.md` and
`memory/project_artifact_bus_invariants.md` for the architectural
decisions this plugin embodies.
