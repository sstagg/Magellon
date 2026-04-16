"""Delete SM Async endpoint + autoscaling + config + model."""
import os
import time

import boto3

PROJECT = os.environ["PROJECT"]
MODEL = f"{PROJECT}-async-model"
CFG = f"{PROJECT}-async-config"
EP = f"{PROJECT}-async-ep"
VARIANT = "primary"

sm = boto3.client("sagemaker")
aas = boto3.client("application-autoscaling")

# Autoscaling first
try:
    aas.deregister_scalable_target(
        ServiceNamespace="sagemaker",
        ResourceId=f"endpoint/{EP}/variant/{VARIANT}",
        ScalableDimension="sagemaker:variant:DesiredInstanceCount",
    )
    print("deregistered autoscaling target")
except Exception as e:
    print(f"  autoscaling: {e}")

try:
    sm.delete_endpoint(EndpointName=EP)
    print("delete_endpoint submitted")
    while True:
        try:
            d = sm.describe_endpoint(EndpointName=EP)
            print(f"  {d['EndpointStatus']}")
            time.sleep(10)
        except sm.exceptions.from_code("ValidationException"):
            break
except sm.exceptions.from_code("ValidationException") as e:
    print(f"  endpoint: {e}")

try:
    sm.delete_endpoint_config(EndpointConfigName=CFG)
    print("deleted config")
except Exception as e:
    print(f"  config: {e}")

try:
    sm.delete_model(ModelName=MODEL)
    print("deleted model")
except Exception as e:
    print(f"  model: {e}")

print("Done.")
