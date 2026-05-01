# test-7-magellon-spa postmortem — first run, May 2026

A short log of what bit us on the first launch. Future re-runners
should read this before following the README.

## TL;DR

Pipeline ran end-to-end with no `magellon-spa` binary on the
instance. Build silently failed at the `git clone` step because the
repo is private. Total cost: ~$0.11 (~10 min × c5.4xlarge).
**Fixed in commit after this** — `02-build-magellon.sh` now scps the
local source tree instead of cloning.

## What bit us

### 1. `/usr/local/bin/cargo` symlink unreadable to ubuntu user

User-data installed Rust under root, then `ln -sf /root/.cargo/bin/* /usr/local/bin/`.
`/root` is mode 700 by default, so the symlink target is unreadable
to the ubuntu user — `cargo --version` from an ssh session reported
"Permission denied".

**Fix shipped:** install Rust *only* as the ubuntu user, then symlink
`/home/ubuntu/.cargo/bin/{cargo,rustc,rustup}` into `/usr/local/bin/`.
ubuntu's home is mode 755 so the symlinks resolve fine.

### 2. `git clone` against a private repo from non-interactive ssh

`02-build-magellon.sh` used:
```bash
git clone --depth 1 https://github.com/khoshbin/magellon-rust-mrc.git
```

The repo is private. Non-interactive ssh sessions can't auth to
GitHub without a deploy key or a token in the env, and the git
client fell back to prompting for a username — there's no TTY, so
it failed with "could not read Username for 'https://github.com':
No such device or address". Build aborted, no binary, all
subsequent stages failed `magellon-spa: No such file or directory`.

**Fix shipped:** `02-build-magellon.sh` now bundles the local
checkout via `tar` + `scp` — sidesteps GitHub auth entirely and is
faster anyway. The local checkout is at
`C:/projects/magellon-rust-mrc` by default; override via
`LOCAL_REPO=/some/other/path bash 02-build-magellon.sh`.

### 3. The pipeline driver kept going after build failure

`10-run-full-pipeline.sh`'s `run()` function explicitly logs but
doesn't abort on per-stage failure — that's the right call when one
stage's failure is recoverable (e.g. CtfRefine failing doesn't
invalidate Refine3D). But when **02 build** fails, every downstream
stage will fail too; the run is wasted compute.

**Future improvement:** add an early `abort if 02 build failed`
guard. Not urgent — the local-source fix means 02 should succeed
deterministically going forward.

## Cost / time accounting

| Item | Charge |
|---|---|
| `c5.4xlarge` × ~12 min | $0.14 |
| 60 GB gp3 EBS × 12 min | < $0.01 |
| Data egress (results bundle ~18 MB) | < $0.01 |
| **Total** | **~$0.15** |

## Re-run

After applying both fixes (commits in this branch), re-run is the
same as the README:

```bash
cd C:/projects/Magellon/CoreService/sandbox/aws/test-7-magellon-spa
# Refresh SSO creds in ../.env first.
bash 00-launch.sh
bash 10-run-full-pipeline.sh
```
