# magellon_stack_maker_plugin

Particle extraction plugin — boxes particles from a micrograph given a
picker's coordinate file, writes a RELION-style `.mrcs` + `.star` +
companion `.json`. Phase 5 deliverable (2026-05-03).

Category: `PARTICLE_EXTRACTION` (code 10).
Backend id: `stack-maker`.
Subject: source micrograph (one task per micrograph).

The algorithm is vendored from `Sandbox/magellon_stack_maker` with two
known integration bugs from `MAGELLON_PARTICLE_PIPELINE.md` fixed in
`plugin/algorithm.py`:

1. RELION `_rlnImageName` token order — now `NNNNNN@stack.mrcs`
   (what the CAN classifier parses), reversed from the original.
2. Pixel size column — now `_rlnImagePixelSize`, what the classifier's
   STAR reader expects.

## Deferred follow-ups (Phase 4 + 5b)

- Phase 4 lands the `artifact` table; `TaskOutputProcessor` then writes
  one `particle_stack` artifact per result and projects
  `particle_stack_id` back onto `output_data`. Until then the plugin
  emits paths only.
- Integration tests against testcontainers RMQ + a synthetic 2D
  micrograph + a tiny picks JSON — copy from the FFT plugin's
  `tests/integration/` once the wire path is ready.

See `Documentation/CATEGORIES_AND_BACKENDS.md` and
`memory/project_artifact_bus_invariants.md` (ratified 2026-05-03) for
the architectural decisions this plugin embodies.
