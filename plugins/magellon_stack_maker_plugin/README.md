# magellon_stack_maker_plugin

Particle extraction plugin. It boxes particles from micrographs given
picker coordinate files, then writes a RELION-style `.mrcs` stack, a
`.star` metadata file, and a companion `.json`.

Category: `PARTICLE_EXTRACTION` (code 10).
Backend id: `stack-maker`.

## Contract Fixes

The vendored algorithm differs from the original sandbox copy in two
important ways:

1. RELION `_rlnImageName` token order is `NNNNNN@stack.mrcs`, which is
   what the CAN classifier parses.
2. Pixel size is written as `_rlnImagePixelSize`.

## Topaz And Batch Handoff

The extractor accepts GUI-saved pick rows (`x` / `y`) and Topaz batch
pick rows (`center: [x, y]`). For a single exposure, pass
`micrograph_path` and `particles_path` normally.

For session-level 2D classification after Topaz batch picking, pass
`engine_opts.batch_manifest_path` pointing to a JSON file:

```json
{
  "items": [
    {
      "micrograph_path": "C:/magellon/gpfs/home/session/original/mic1.mrc",
      "particles_path": "C:/magellon/gpfs/home/session/topazparticlepicking/mic1/picks.json"
    }
  ]
}
```

All listed micrograph/picks pairs are boxed into one aggregate
classifier-ready stack and one STAR file. `engine_opts.output_stem`
can override the output basename.

## Deferred Follow-Ups

- Core/GUI should generate the batch manifest from selected Topaz pick
  runs and dispatch `stack-maker` through the generic plugin job API.
- `TaskOutputProcessor` writes the `particle_stack` artifact and
  projects `particle_stack_id` back onto `output_data`.
- A larger live-broker integration test should cover the full
  Topaz -> stack-maker -> CAN route once the GUI orchestration lands.
