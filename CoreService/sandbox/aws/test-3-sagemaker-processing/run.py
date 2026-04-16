"""Run a SageMaker Processing job against our motioncor image.

Inputs:
  s3://motioncortest/Magellon-test/Magellon-test/example1/20241203_54530_integrated_movie.mrc.tif
Outputs:
  s3://magellon-gpu-eval-work/test-3-sm-processing/<job_name>/
"""
import os
import time

import boto3

ACCOUNT = os.environ["AWS_ACCOUNT_ID"]
REGION = os.environ["AWS_DEFAULT_REGION"]
PROJECT = os.environ["PROJECT"]
IMAGE = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/{PROJECT}/motioncor:latest"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/{PROJECT}-sagemaker-exec-role"
WORK_BUCKET = "magellon-gpu-eval-work"

INPUT_BUCKET = "motioncortest"
INPUT_KEY = "Magellon-test/Magellon-test/example1/20241203_54530_integrated_movie.mrc.tif"

JOB_NAME = f"{PROJECT}-proc-{time.strftime('%Y%m%d-%H%M%S')}"
OUT_S3 = f"s3://{WORK_BUCKET}/test-3-sm-processing/{JOB_NAME}"

sm = boto3.client("sagemaker")

print(f"Starting Processing job {JOB_NAME}")
resp = sm.create_processing_job(
    ProcessingJobName=JOB_NAME,
    ProcessingResources={
        "ClusterConfig": {
            "InstanceCount": 1,
            "InstanceType": "ml.g4dn.2xlarge",
            "VolumeSizeInGB": 40,
        },
    },
    AppSpecification={
        "ImageUri": IMAGE,
        "ContainerEntrypoint": ["python3", "/app/run_motioncor.py", "sm-processing"],
    },
    ProcessingInputs=[{
        "InputName": "movie",
        "S3Input": {
            "S3Uri": f"s3://{INPUT_BUCKET}/{INPUT_KEY}",
            "LocalPath": "/opt/ml/processing/input/movie",
            "S3DataType": "S3Prefix",
            "S3InputMode": "File",
            "S3DataDistributionType": "FullyReplicated",
        },
    }],
    ProcessingOutputConfig={
        "Outputs": [{
            "OutputName": "corrected",
            "S3Output": {
                "S3Uri": OUT_S3,
                "LocalPath": "/opt/ml/processing/output",
                "S3UploadMode": "EndOfJob",
            },
        }],
    },
    RoleArn=ROLE_ARN,
    StoppingCondition={"MaxRuntimeInSeconds": 1800},
    Tags=[
        {"Key": "Project", "Value": PROJECT},
        {"Key": "Owner", "Value": os.environ.get("OWNER", "")},
        {"Key": "CostCenter", "Value": os.environ.get("COST_CENTER", "")},
    ],
)

print(f"ARN: {resp['ProcessingJobArn']}")

prev = None
t0 = time.time()
while True:
    d = sm.describe_processing_job(ProcessingJobName=JOB_NAME)
    status = d["ProcessingJobStatus"]
    if status != prev:
        print(f"  +{int(time.time()-t0)}s  {status}  {d.get('FailureReason','')}")
        prev = status
    if status in ("Completed", "Failed", "Stopped"):
        break
    time.sleep(10)

print()
d = sm.describe_processing_job(ProcessingJobName=JOB_NAME)
created = d.get("CreationTime")
started = d.get("ProcessingStartTime")
ended = d.get("ProcessingEndTime") or d.get("LastModifiedTime")
print(f"status: {d['ProcessingJobStatus']}  reason: {d.get('FailureReason','(none)')}")

if started and created:
    print(f"provision:  {(started - created).total_seconds():.1f}s")
if ended and started:
    run_s = (ended - started).total_seconds()
    print(f"run time:   {run_s:.1f}s")
    # ml.g4dn.2xlarge on-demand: ~$1.0515/hr (40% markup over raw EC2 g4dn.2xlarge $0.752/hr)
    print(f"cost (ml.g4dn.2xlarge on-demand $1.0515/hr): ${run_s * 1.0515 / 3600:.4f}")
print(f"\nOutputs: {OUT_S3}/")
