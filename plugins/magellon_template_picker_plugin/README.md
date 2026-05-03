# magellon_template_picker_plugin

External (broker-resident) FFT-correlation template-matching particle
picker. Phase 6 deliverable (2026-05-03).

Category: `PARTICLE_PICKING` (code 3).
Backend id: `template-picker`.
Cardinality: per-micrograph (one task per image).

## Why an external version when one already runs in-process?

`CoreService/plugins/pp/template_picker/` already serves the
PARTICLE_PICKING category in-process. Per architecture principle 4
(every abstraction pays its way today), this external version is
justified when a deployment needs:

- **Independent picker scaling.** The in-process picker shares the
  CoreService thread pool; an external replica scales orthogonally.
- **Different host placement.** A CPU-heavy box near the data plane
  while CoreService runs on the API host.

If neither driver applies, prefer the in-process path. Both backends
register against the same category; the dispatcher's backend axis
(X.1, 2026-04-27) routes to the named one via
`TaskMessage.target_backend`.

## What ships now

- `plugin/algorithm.py` — vendored from
  `Sandbox/magellon_template_picker/picker.py` (409 lines).
- `plugin/compute.py` — file I/O + parameter mapping
  (`_load_mrc`, `_resolve_template_paths`, `run_template_pick`).
- `plugin/plugin.py` — `TemplatePickerPlugin` (SDK contract) +
  `build_pick_result`.
- Standard FFT-blueprint scaffolding (Dockerfile, manifest.yaml,
  configs, requirements.txt).

## Inputs

The plugin uses `CryoEmImageInput`. Picker-specific knobs ride on
`engine_opts`:

| Key | Required | Default | Notes |
|---|---|---|---|
| `templates` | yes | — | Path / list / glob of template MRCs |
| `diameter_angstrom` | yes | — | Particle diameter |
| `pixel_size_angstrom` | yes | — | Micrograph pixel size |
| `template_pixel_size_angstrom` | no | `pixel_size_angstrom` | Templates rescaled if mismatch |
| `threshold` | no | 0.4 | Correlation threshold |
| `bin` | no | 1 | Power-of-two image binning |
| `max_peaks` | no | 500 | NMS cap |
| `angle_ranges` | no | `[(0, 360, 10)]` per template | Rotation sweep |

## Outputs

- `particles.json` — list of `{x, y, score, angle, ...}` dicts.
- `ParticlePickingOutput.particles_json_path` — the path on the data
  plane. Per ratified rule 1 (refs only on bus), the inline `picks`
  list is left empty even for small results.
