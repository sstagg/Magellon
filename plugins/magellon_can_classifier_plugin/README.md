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

## Phase 7 status — scaffold only

This commit ships:

- The SDK contract: `TWO_D_CLASSIFICATION_CATEGORY`,
  `TwoDClassificationInput`, `TwoDClassificationOutput`.
- The plugin shell (`PluginBrokerRunner` glue, manifest, configs,
  Dockerfile, requirements).
- Contract pin tests against the SDK.

It does **not** ship:

- The 1714-line CAN algorithm — vendor target is `plugin/algorithm.py`,
  source is `Sandbox/magellon_can_classifier/{classifier,cli}.py`.
  `compute.classify_stack` raises `NotImplementedError` until Phase 7b
  vendors it.
- Torch / GPU runtime in the Docker image. Phase 7b switches the base
  to `nvidia/cuda:12.1-runtime` and adds the algorithm deps.
- Phase 3 / Phase 4 wiring: subject_id is still passed via
  `TwoDClassificationInput.particle_stack_id` (not via
  `TaskMessage.subject_id` yet); `TaskOutputProcessor` doesn't yet
  write a `class_averages` artifact.

Plugin contract tests (`tests/test_can_classifier_plugin.py`) mock
`compute.classify_stack` and verify the SDK plumbing — they pass
without the algorithm vendored.

## Phase 7b checklist

1. Copy `Sandbox/magellon_can_classifier/{classifier,cli}.py` into
   `plugin/algorithm.py` (split into a subpackage if size warrants).
2. Update `compute.classify_stack` to delegate to
   `algorithm.run_align_and_can(...)`.
3. Add `torch`, `scikit-image`, `scikit-learn`, `pandas`, `mrcfile` to
   `requirements.txt` / `pyproject.toml`.
4. Switch the Dockerfile base to a CUDA runtime image.
5. Add an integration test that runs a tiny `(N=20, num_classes=2)`
   stack through the full path on CPU.

See `Documentation/CATEGORIES_AND_BACKENDS.md` and
`memory/project_artifact_bus_invariants.md` for the architectural
decisions this plugin embodies.
