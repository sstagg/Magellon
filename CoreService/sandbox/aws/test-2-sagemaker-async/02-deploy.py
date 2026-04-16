"""Create SM Async endpoint with scale-to-zero."""
import os
import time

import boto3

ACCOUNT = os.environ["AWS_ACCOUNT_ID"]
REGION = os.environ["AWS_DEFAULT_REGION"]
PROJECT = os.environ["PROJECT"]

IMAGE = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/{PROJECT}/motioncor-sm-async:latest"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/{PROJECT}-sagemaker-exec-role"
WORK_BUCKET = "magellon-gpu-eval-work"
OUT_S3 = f"s3://{WORK_BUCKET}/test-2-sm-async/output/"
FAIL_S3 = f"s3://{WORK_BUCKET}/test-2-sm-async/failure/"

MODEL = f"{PROJECT}-async-model"
CFG = f"{PROJECT}-async-config"
EP = f"{PROJECT}-async-ep"
VARIANT = "primary"

sm = boto3.client("sagemaker")
aas = boto3.client("application-autoscaling")

print("Creating Model...")
try:
    sm.create_model(
        ModelName=MODEL,
        ExecutionRoleArn=ROLE_ARN,
        PrimaryContainer={"Image": IMAGE, "Mode": "SingleModel"},
        Tags=[{"Key": "Project", "Value": PROJECT}, {"Key": "Owner", "Value": os.environ.get("OWNER", "")}],
    )
except sm.exceptions.from_code("ValidationException") as e:
    if "Cannot create already existing" in str(e):
        print("  model exists")
    else:
        raise

print("Creating EndpointConfig (async)...")
try:
    sm.create_endpoint_config(
        EndpointConfigName=CFG,
        ProductionVariants=[{
            "VariantName": VARIANT,
            "ModelName": MODEL,
            "InstanceType": "ml.g4dn.2xlarge",
            "InitialInstanceCount": 1,
        }],
        AsyncInferenceConfig={
            "OutputConfig": {"S3OutputPath": OUT_S3, "S3FailurePath": FAIL_S3},
            "ClientConfig": {"MaxConcurrentInvocationsPerInstance": 2},
        },
        Tags=[{"Key": "Project", "Value": PROJECT}],
    )
except sm.exceptions.from_code("ValidationException") as e:
    if "already existing" in str(e):
        print("  config exists")
    else:
        raise

print("Creating Endpoint (2-5 min)...")
try:
    sm.create_endpoint(EndpointName=EP, EndpointConfigName=CFG,
                       Tags=[{"Key": "Project", "Value": PROJECT}])
except sm.exceptions.from_code("ValidationException") as e:
    if "already existing" in str(e):
        print("  endpoint exists")
    else:
        raise

t0 = time.time()
prev = None
while True:
    d = sm.describe_endpoint(EndpointName=EP)
    st = d["EndpointStatus"]
    if st != prev:
        print(f"  +{int(time.time()-t0)}s  {st}")
        prev = st
    if st == "InService":
        break
    if st == "Failed":
        raise SystemExit(d.get("FailureReason"))
    time.sleep(15)

print("Configuring scale-to-zero...")
resource_id = f"endpoint/{EP}/variant/{VARIANT}"
aas.register_scalable_target(
    ServiceNamespace="sagemaker",
    ResourceId=resource_id,
    ScalableDimension="sagemaker:variant:DesiredInstanceCount",
    MinCapacity=0,
    MaxCapacity=2,
)
aas.put_scaling_policy(
    PolicyName=f"{EP}-scale-on-invocations",
    ServiceNamespace="sagemaker",
    ResourceId=resource_id,
    ScalableDimension="sagemaker:variant:DesiredInstanceCount",
    PolicyType="TargetTrackingScaling",
    TargetTrackingScalingPolicyConfiguration={
        "TargetValue": 5.0,  # backlog per instance
        "CustomizedMetricSpecification": {
            "MetricName": "ApproximateBacklogSizePerInstance",
            "Namespace": "AWS/SageMaker",
            "Dimensions": [{"Name": "EndpointName", "Value": EP}],
            "Statistic": "Average",
        },
        "ScaleInCooldown": 600,
        "ScaleOutCooldown": 300,
    },
)
print(f"Endpoint {EP} ready. OutputPath: {OUT_S3}")
