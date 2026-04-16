"""Single Lambda handling upload/status/download actions via Function URL.

Env:
  WORK_BUCKET   S3 bucket for uploads and outputs
  API_KEY       Shared secret. Required in header X-Api-Key.
  BATCH_QUEUE   Batch job queue name (for status lookup fallback)

Actions (POST body JSON):
  {"action":"mint_upload",   "filename":"movie.tif", "content_type":"..."}
  {"action":"status",        "job_id":"<uuid>"}
  {"action":"mint_download", "job_id":"<uuid>"}
"""
import json
import os
import re
import uuid

import boto3

s3 = boto3.client("s3")
batch = boto3.client("batch")

BUCKET = os.environ["WORK_BUCKET"]
API_KEY = os.environ["API_KEY"]
BATCH_QUEUE = os.environ.get("BATCH_QUEUE", "")

UPLOAD_TTL = 3600      # 1h
DOWNLOAD_TTL = 3600    # 1h
UUID_RE = re.compile(r"^[0-9a-f-]{36}$")


def resp(code: int, body: dict) -> dict:
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, X-Api-Key",
        },
        "body": json.dumps(body),
    }


def handler(event, _context):
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}

    if (event.get("requestContext", {}).get("http", {}).get("method")) == "OPTIONS":
        return resp(204, {})

    if headers.get("x-api-key") != API_KEY:
        return resp(401, {"error": "bad or missing X-Api-Key"})

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return resp(400, {"error": "invalid JSON body"})

    action = body.get("action")
    try:
        if action == "mint_upload":
            return mint_upload(body)
        if action == "status":
            return status(body)
        if action == "mint_download":
            return mint_download(body)
        return resp(400, {"error": f"unknown action: {action}"})
    except Exception as e:
        return resp(500, {"error": str(e)})


def mint_upload(body: dict) -> dict:
    filename = body.get("filename") or "upload.tif"
    filename = filename.replace("..", "_").replace("/", "_")
    content_type = body.get("content_type") or "application/octet-stream"
    job_id = str(uuid.uuid4())
    key = f"uploads/{job_id}/{filename}"

    url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=UPLOAD_TTL,
    )
    return resp(200, {
        "job_id": job_id,
        "key": key,
        "upload_url": url,
        "expires_in": UPLOAD_TTL,
        "content_type_required": content_type,
    })


def status(body: dict) -> dict:
    job_id = body.get("job_id") or ""
    if not UUID_RE.match(job_id):
        return resp(400, {"error": "bad job_id"})

    # Find the AWS Batch job by our JobId tag (easier: we also write status files
    # from on_upload for deterministic lookup).
    out_prefix = f"outputs/{job_id}/"
    out = s3.list_objects_v2(Bucket=BUCKET, Prefix=out_prefix).get("Contents", [])
    if out:
        return resp(200, {
            "job_id": job_id,
            "status": "SUCCEEDED",
            "output_count": len(out),
        })

    # Fall back to Batch API
    if BATCH_QUEUE:
        try:
            jobs = batch.list_jobs(jobQueue=BATCH_QUEUE, filters=[
                {"name": "JOB_NAME", "values": [f"upload-{job_id[:8]}*"]}
            ]).get("jobSummaryList", [])
            if jobs:
                # Pick latest
                j = sorted(jobs, key=lambda x: x.get("createdAt", 0))[-1]
                return resp(200, {"job_id": job_id, "status": j.get("status"), "reason": j.get("statusReason")})
        except Exception:
            pass

    return resp(200, {"job_id": job_id, "status": "UNKNOWN"})


def mint_download(body: dict) -> dict:
    job_id = body.get("job_id") or ""
    if not UUID_RE.match(job_id):
        return resp(400, {"error": "bad job_id"})
    out_prefix = f"outputs/{job_id}/"
    objs = s3.list_objects_v2(Bucket=BUCKET, Prefix=out_prefix).get("Contents", [])
    if not objs:
        return resp(404, {"error": "no outputs yet — job pending or failed"})
    urls = []
    for o in objs:
        u = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": o["Key"]},
            ExpiresIn=DOWNLOAD_TTL,
        )
        urls.append({"key": o["Key"], "size": o["Size"], "url": u})
    return resp(200, {"job_id": job_id, "download_urls": urls, "expires_in": DOWNLOAD_TTL})
