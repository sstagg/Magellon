"""SageMaker-compatible FastAPI server. Thin wrapper over run_motioncor.py helpers."""
import json
import os
import sys
import time
import uuid
from pathlib import Path

import boto3
from fastapi import FastAPI, Request

sys.path.insert(0, "/app")
from run_motioncor import (  # type: ignore
    INPUT_DIR, OUTPUT_DIR, download, parse_s3, run_binary, upload_dir,
)

app = FastAPI()
s3 = boto3.client("s3")


@app.get("/ping")
def ping():
    return {"ok": True}


@app.post("/invocations")
async def invocations(req: Request):
    t0 = time.time()
    body = await req.json()
    in_s3 = body.get("input_s3")
    out_prefix = body.get("output_prefix_s3")
    gain_s3 = body.get("gain_s3")
    job_id = body.get("job_id") or str(uuid.uuid4())[:8]
    extra = body.get("args") or []
    if not in_s3 or not out_prefix:
        return {"status": "error", "error": "input_s3 and output_prefix_s3 required"}

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    in_tif = download(s3, in_s3, INPUT_DIR / Path(parse_s3(in_s3)[1]).name)
    gain = download(s3, gain_s3, INPUT_DIR / Path(parse_s3(gain_s3)[1]).name) if gain_s3 else None

    out_prefix_local = OUTPUT_DIR / f"{job_id}_{in_tif.stem}"
    try:
        run_binary(in_tif, gain, out_prefix_local, extra)
    except SystemExit as e:
        return {"status": "error", "error": f"motioncor exit {e.code}"}

    uploaded = upload_dir(s3, OUTPUT_DIR, f"{out_prefix.rstrip('/')}/{job_id}")
    return {
        "status": "ok",
        "job_id": job_id,
        "outputs": uploaded,
        "seconds": round(time.time() - t0, 2),
    }
