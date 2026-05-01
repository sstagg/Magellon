# test-6-relion — RELION 5 in a box

A proof-of-life test that we can run RELION 5 end-to-end on a single
GPU instance. Goal:

1. Verify the install path (build from source on Deep Learning AMI).
2. Run **Class2D** on the official RELION 5 tutorial dataset → produce
   25 class averages.
3. Run **Class3D** with K=4 → produce 4 reconstructions.
4. Run **Refine3D** with `--auto_refine --split_random_halves` → produce
   the headline gold-standard reconstruction.
5. Run **PostProcess** → final sharpened map + FSC + resolution.
6. Capture all outputs to S3 + tear down.

Tear down only happens at the end (`99-teardown.sh`); the instance
stays alive across all jobs so we don't reinstall RELION every time.

## Account / cost context

- Account: 789438509093 (FSU SSO)
- Region: us-east-1
- Instance: **g5.2xlarge on-demand** — 1× NVIDIA A10G 24 GB, 8 vCPU, 32 GB RAM. ~$1.21/hr.
- Dataset: ~3 GB RELION 5 tutorial (β-galactosidase subset) on a 80 GB gp3 root volume.
- Budget: comfortably inside the existing $50/mo cap. Single full pipeline run ≈ $3–4 wall-clock cost.

Note we deliberately use **on-demand**, not spot — Refine3D's
~45-minute runtime is too long to risk a spot interruption.

## Layout

```
00-launch.sh         spin up instance, run user-data (build RELION + nvidia toolkit), wait SSH
00-userdata.sh       embedded into 00-launch via heredoc; the build script
01-fetch-data.sh     download RELION 5 tutorial dataset to /data on the instance
02-class2d.sh        Class2D, 25 classes, 5 iterations (~10 min)
03-class3d.sh        Class3D, K=4, 5 iterations (~20 min)
04-refine3d.sh       Refine3D --auto_refine --split_random_halves (~45 min)
05-postprocess.sh    PostProcess on the Refine3D output
06-fetch-results.sh  rsync the relevant outputs back to outputs/
99-teardown.sh       terminate instance, delete SG + key pair
```

## Each script writes `.instance-env` so subsequent steps reuse the same instance.

## Quickstart

```bash
# Source SSO creds first (or export AWS_ACCESS_KEY_ID/SECRET/SESSION_TOKEN)
source ../common/activate.sh

./00-launch.sh
./01-fetch-data.sh
./02-class2d.sh        # ~10 min, smallest test
./03-class3d.sh        # ~20 min
./04-refine3d.sh       # ~45 min
./05-postprocess.sh    # ~1 min
./06-fetch-results.sh  # pull outputs to outputs/
./99-teardown.sh       # only at the very end
```

## Success criteria

| Step | Criterion |
|---|---|
| 00-launch | RELION binary `/opt/relion/bin/relion_refine` exists and prints version |
| 02-class2d | `Class2D/run_it005_classes.mrcs` exists, 25 classes look like β-galactosidase |
| 03-class3d | `Class3D/run_it005_class00{1,2,3,4}.mrc` all written |
| 04-refine3d | `Refine3D/run_class001.mrc` written with reported resolution < 5 Å |
| 05-postprocess | Final FSC = 0.143 resolution reported |

If any step fails, instance stays up so we can SSH in and debug.
