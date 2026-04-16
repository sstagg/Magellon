"""MotionCor2 runner: download input from S3, run, upload outputs to S3.

Modes:
  env     — read MOTIONCOR_* env vars (used by Batch / EC2 spot)
  sm-processing — read fixed SageMaker Processing paths (/opt/ml/processing/{input,output})

Env vars (env mode):
  MOTIONCOR_INPUT_S3        s3://bucket/key of the .tif movie (required)
  MOTIONCOR_GAIN_S3         s3://bucket/key of gain ref (optional)
  MOTIONCOR_OUTPUT_PREFIX   s3://bucket/prefix for outputs (required)
  MOTIONCOR_ARGS            extra CLI args passed to MotionCor2 (default: minimal defaults)
  MOTIONCOR_JOB_ID          identifies this run in logs/output paths (default: random uuid)

Exit codes:
  0  ok
  2  bad args
  3  download failed
  4  motioncor failed
  5  upload failed
"""
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

BINARY = "/app/MotionCor2"
INPUT_DIR = Path("/tmp/motioncor_in")
OUTPUT_DIR = Path("/tmp/motioncor_out")


def log(event: str, **kv) -> None:
    kv.update(event=event, ts=time.time())
    print(json.dumps(kv), flush=True)


def parse_s3(uri: str) -> tuple[str, str]:
    p = urlparse(uri)
    if p.scheme != "s3" or not p.netloc:
        raise ValueError(f"not an s3:// uri: {uri}")
    return p.netloc, p.path.lstrip("/")


def download(s3, uri: str, dst: Path) -> Path:
    bucket, key = parse_s3(uri)
    dst.parent.mkdir(parents=True, exist_ok=True)
    log("download_start", src=uri, dst=str(dst))
    t0 = time.time()
    s3.download_file(bucket, key, str(dst))
    log("download_done", src=uri, bytes=dst.stat().st_size, seconds=round(time.time() - t0, 2))
    return dst


def upload_dir(s3, src_dir: Path, prefix_uri: str) -> list[str]:
    bucket, prefix = parse_s3(prefix_uri)
    uploaded = []
    for p in src_dir.rglob("*"):
        if not p.is_file():
            continue
        key = f"{prefix.rstrip('/')}/{p.relative_to(src_dir).as_posix()}"
        log("upload_start", dst=f"s3://{bucket}/{key}", bytes=p.stat().st_size)
        t0 = time.time()
        s3.upload_file(str(p), bucket, key)
        log("upload_done", dst=f"s3://{bucket}/{key}", seconds=round(time.time() - t0, 2))
        uploaded.append(f"s3://{bucket}/{key}")
    return uploaded


def run_binary(in_tif: Path, gain: Path | None, out_prefix: Path, extra: list[str]) -> None:
    # Minimal defaults — matches the existing plugin's utils.build_motioncor3_command and the
    # benchmark script in s3://motioncortest/Magellon-test/Magellon-test/script.sh.
    cmd = [BINARY, "-InTiff", str(in_tif), "-OutMrc", f"{out_prefix}.mrc",
           "-Patch", "5", "5", "-Iter", "10", "-Tol", "0.5", "-Gpu", "0"]
    if gain:
        cmd += ["-Gain", str(gain)]
    cmd += extra

    # Write MC2 output to disk so a SIGKILL-before-pipe-flush doesn't eat the diagnostic output.
    # (glibc fully-buffers stdout when it's a pipe; a kill wipes the buffer — we saw empty tails.)
    stdout_path = Path("/tmp/mc2_stdout.log")
    stderr_path = Path("/tmp/mc2_stderr.log")

    log("motioncor_start", cmd=" ".join(cmd))
    t0 = time.time()
    with stdout_path.open("wb") as so, stderr_path.open("wb") as se:
        r = subprocess.run(cmd, stdout=so, stderr=se)
    dt = round(time.time() - t0, 2)

    def tail(p: Path, n: int = 4000) -> str:
        try:
            data = p.read_bytes()[-n:]
            return data.decode("utf-8", errors="replace")
        except Exception as e:
            return f"<read-failed: {e}>"

    log("motioncor_done", rc=r.returncode, seconds=dt,
        stdout_tail=tail(stdout_path), stderr_tail=tail(stderr_path))
    if r.returncode != 0:
        sys.exit(4)


def run_env_mode() -> None:
    in_s3 = os.environ.get("MOTIONCOR_INPUT_S3")
    out_prefix_s3 = os.environ.get("MOTIONCOR_OUTPUT_PREFIX")
    gain_s3 = os.environ.get("MOTIONCOR_GAIN_S3") or None
    extra_args = os.environ.get("MOTIONCOR_ARGS", "").split() if os.environ.get("MOTIONCOR_ARGS") else []
    job_id = os.environ.get("MOTIONCOR_JOB_ID", str(uuid.uuid4())[:8])

    if not in_s3 or not out_prefix_s3:
        log("bad_args", reason="MOTIONCOR_INPUT_S3 and MOTIONCOR_OUTPUT_PREFIX are required")
        sys.exit(2)

    s3 = boto3.client("s3")
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        in_tif = download(s3, in_s3, INPUT_DIR / Path(parse_s3(in_s3)[1]).name)
        gain = download(s3, gain_s3, INPUT_DIR / Path(parse_s3(gain_s3)[1]).name) if gain_s3 else None
    except ClientError as e:
        log("download_fail", error=str(e))
        sys.exit(3)

    out_prefix_local = OUTPUT_DIR / f"{job_id}_{in_tif.stem}"
    run_binary(in_tif, gain, out_prefix_local, extra_args)

    try:
        uploaded = upload_dir(s3, OUTPUT_DIR, f"{out_prefix_s3.rstrip('/')}/{job_id}")
    except ClientError as e:
        log("upload_fail", error=str(e))
        sys.exit(5)

    log("job_complete", job_id=job_id, outputs=uploaded)


def run_sm_processing_mode() -> None:
    """SageMaker Processing mounts inputs at /opt/ml/processing/input/<channel>,
    uploads /opt/ml/processing/output/<channel> to S3 for us."""
    in_root = Path("/opt/ml/processing/input")
    out_root = Path("/opt/ml/processing/output")
    out_root.mkdir(parents=True, exist_ok=True)

    # Expect a single .tif under input/, and an optional gain under input-gain/
    tifs = list((in_root / "movie").glob("*.tif"))
    if not tifs:
        log("bad_args", reason=f"no .tif under {in_root}/movie")
        sys.exit(2)
    in_tif = tifs[0]
    gain_candidates = list((in_root / "gain").glob("*.tif")) if (in_root / "gain").exists() else []
    gain = gain_candidates[0] if gain_candidates else None

    out_prefix = out_root / f"{in_tif.stem}_corrected"
    run_binary(in_tif, gain, out_prefix, [])
    log("job_complete", mode="sm-processing")


def run_diag_mode() -> None:
    """Report GPU + binary linkage + bare MotionCor2 invocation so we can see what SIGKILL is
    happening to. Never fails — always exits 0 so we get full logs."""
    for step, cmd in [
        ("nvidia-smi",       ["nvidia-smi"]),
        ("ldd-motioncor",    ["ldd", BINARY]),
        ("motioncor-help",   [BINARY]),  # no args → MC2 1.6.x prints usage and exits cleanly
    ]:
        log("diag_step_start", step=step, cmd=" ".join(cmd))
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True)
        log("diag_step_done", step=step, rc=r.returncode, seconds=round(time.time() - t0, 2),
            stdout_tail=r.stdout[-2000:], stderr_tail=r.stderr[-1000:])


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "env"
    if mode == "env":
        run_env_mode()
    elif mode == "sm-processing":
        run_sm_processing_mode()
    elif mode == "diag":
        run_diag_mode()
    else:
        log("bad_args", reason=f"unknown mode {mode}")
        sys.exit(2)
