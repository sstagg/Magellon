"""Invoke the SM Async endpoint with a small JSON payload (S3 URIs) and wait for output."""
import json
import os
import time
import uuid
from urllib.parse import urlparse

import boto3

PROJECT = os.environ["PROJECT"]
WORK_BUCKET = "magellon-gpu-eval-work"
EP = f"{PROJECT}-async-ep"

INPUT_S3 = f"s3://motioncortest/Magellon-test/Magellon-test/example1/20241203_54530_integrated_movie.mrc.tif"
OUTPUT_PREFIX = f"s3://{WORK_BUCKET}/test-2-sm-async/results/"
JOB_ID = f"async-{time.strftime('%Y%m%d-%H%M%S')}"

s3 = boto3.client("s3")
rt = boto3.client("sagemaker-runtime")

# 1. Upload request payload (small JSON) to S3 — async endpoint input must come from S3
payload = json.dumps({"input_s3": INPUT_S3, "output_prefix_s3": OUTPUT_PREFIX, "job_id": JOB_ID}).encode()
payload_key = f"test-2-sm-async/payloads/{uuid.uuid4()}.json"
s3.put_object(Bucket=WORK_BUCKET, Key=payload_key, Body=payload, ContentType="application/json")
payload_uri = f"s3://{WORK_BUCKET}/{payload_key}"
print(f"Payload: {payload_uri}")

# 2. Invoke async
print("Invoking endpoint...")
t0 = time.time()
r = rt.invoke_endpoint_async(
    EndpointName=EP,
    InputLocation=payload_uri,
    InferenceId=JOB_ID,
    ContentType="application/json",
)
inference_id = r["InferenceId"]
output_location = r["OutputLocation"]
failure_location = r.get("FailureLocation")
print(f"InferenceId: {inference_id}")
print(f"Output will land at: {output_location}")

# 3. Poll S3 for output object
print("Polling for result (ok: output_location, fail: failure_location)...")
p = urlparse(output_location)
out_bucket, out_key = p.netloc, p.path.lstrip("/")
f = urlparse(failure_location) if failure_location else None

prev = ""
while True:
    status = "waiting"
    try:
        s3.head_object(Bucket=out_bucket, Key=out_key)
        status = "ready"
    except s3.exceptions.ClientError:
        if f:
            try:
                s3.head_object(Bucket=f.netloc, Key=f.path.lstrip("/"))
                status = "failed"
            except s3.exceptions.ClientError:
                pass
    msg = f"{int(time.time()-t0)}s  {status}"
    if msg != prev:
        print(f"  {msg}")
        prev = msg
    if status in ("ready", "failed"):
        break
    time.sleep(10)
    if time.time() - t0 > 900:
        print("TIMEOUT (15 min)")
        break

# 4. Print result
if status == "ready":
    body = s3.get_object(Bucket=out_bucket, Key=out_key)["Body"].read().decode()
    print(f"\n=== Output JSON ===\n{body}")
elif status == "failed":
    body = s3.get_object(Bucket=f.netloc, Key=f.path.lstrip("/"))["Body"].read().decode()
    print(f"\n=== Failure ===\n{body}")

print(f"\nTotal elapsed: {time.time()-t0:.1f}s")
