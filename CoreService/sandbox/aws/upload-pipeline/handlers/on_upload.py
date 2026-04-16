"""S3 event → submit Batch job. Key convention: uploads/<job_id>/<filename>.

Env:
  BATCH_QUEUE
  BATCH_JOB_DEF
  WORK_BUCKET
"""
import os
import re

import boto3

batch = boto3.client("batch")
WORK_BUCKET = os.environ["WORK_BUCKET"]
QUEUE = os.environ["BATCH_QUEUE"]
JOB_DEF = os.environ["BATCH_JOB_DEF"]

KEY_RE = re.compile(r"^uploads/(?P<job_id>[0-9a-f-]{36})/(?P<filename>.+)$")


def handler(event, _context):
    submitted = []
    for rec in event.get("Records", []):
        bucket = rec["s3"]["bucket"]["name"]
        key = rec["s3"]["object"]["key"]
        m = KEY_RE.match(key)
        if not m:
            print(f"skip non-matching key: {key}")
            continue
        job_id = m.group("job_id")
        input_s3 = f"s3://{bucket}/{key}"
        output_prefix = f"s3://{WORK_BUCKET}/outputs/{job_id}/"

        resp = batch.submit_job(
            jobName=f"upload-{job_id[:8]}",
            jobQueue=QUEUE,
            jobDefinition=JOB_DEF,
            containerOverrides={
                "environment": [
                    {"name": "MOTIONCOR_INPUT_S3", "value": input_s3},
                    {"name": "MOTIONCOR_OUTPUT_PREFIX", "value": output_prefix},
                    {"name": "MOTIONCOR_JOB_ID", "value": job_id},
                ]
            },
            tags={"Project": "magellon-gpu-eval", "Source": "upload-pipeline", "JobId": job_id},
        )
        print(f"submitted {resp['jobId']} for {input_s3}")
        submitted.append(resp["jobId"])
    return {"submitted": submitted}
