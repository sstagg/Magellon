import boto3, os, time, datetime, sys

os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
# Credentials from environment: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN

BUCKET  = 'magellon-gpu-eval-work'
SESSION = '24dec03a'
IID     = 'i-01b4296a6b7c450c2'
LAUNCH  = datetime.datetime(2026, 5, 19, 22, 3)

s3  = boto3.client('s3',  region_name='us-east-1')
ec2 = boto3.client('ec2', region_name='us-east-1')

def s3_keys(prefix):
    r = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
    return [o['Key'] for o in r.get('Contents', [])]

def instance_state():
    r = ec2.describe_instances(InstanceIds=[IID])
    return r['Reservations'][0]['Instances'][0]['State']['Name']

print('Polling every 90s (max 120 min) for STARTED then ALL_DONE...', flush=True)
started = False
for tick in range(80):  # 80 × 90s = 120 min
    time.sleep(90)
    elapsed = int((datetime.datetime.utcnow() - LAUNCH).total_seconds() / 60)
    try:
        state   = instance_state()
        status  = s3_keys(f'{SESSION}/status/')
        results = s3_keys(f'{SESSION}/results/')
        print(f'[~{elapsed}m] state={state} | status={len(status)} | results={len(results)}', flush=True)

        if not started and any('run.log' in k for k in status):
            started = True
            print(f'  *** STARTED marker found at ~{elapsed}m ***', flush=True)

        if any('ALL_DONE' in k for k in status):
            print(f'  *** ALL_DONE at ~{elapsed}m! results={len(results)} ***', flush=True)
            sys.exit(0)

        if state in ('terminated', 'stopped') and not any('ALL_DONE' in k for k in status):
            if elapsed > 10:  # give it time to write final markers
                print(f'Instance stopped unexpectedly (no ALL_DONE)', flush=True)
                print(f'status files: {status}', flush=True)
                sys.exit(1)
    except Exception as e:
        print(f'[~{elapsed}m] error: {e}', flush=True)

print('Timeout after 120 min — no ALL_DONE', flush=True)
sys.exit(1)
