"""Monitor v16 EC2 MotionCor run."""
import boto3, os, time, datetime, sys

os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

BUCKET     = 'magellon-gpu-eval-work'
SESSION    = '24dec03a'
IID        = 'i-00c48b61afd5da7a9'
LAUNCH_UTC = datetime.datetime(2026, 5, 21, 8, 0, tzinfo=datetime.timezone.utc)

s3  = boto3.client('s3',  region_name='us-east-1')
ec2 = boto3.client('ec2', region_name='us-east-1')

def s3_objs(prefix):
    r = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
    return r.get('Contents', [])

def instance_state():
    r = ec2.describe_instances(InstanceIds=[IID])
    return r['Reservations'][0]['Instances'][0]['State']['Name']

print('Polling every 90s for v16 STARTED/ALL_DONE (up to 100 min)...', flush=True)

last_results = 0
for tick in range(70):
    time.sleep(90)
    elapsed = int((datetime.datetime.now(datetime.timezone.utc) - LAUNCH_UTC).total_seconds() / 60)
    try:
        state        = instance_state()
        ok_results   = [o for o in s3_objs(f'{SESSION}/results/')
                        if o['LastModified'] > LAUNCH_UTC]
        ok_statuses  = [o for o in s3_objs(f'{SESSION}/status/')
                        if o['Key'].endswith('.status') and o['LastModified'] > LAUNCH_UTC]
        all_done_obj = [o for o in s3_objs(f'{SESSION}/status/')
                        if 'ALL_DONE' in o['Key'] and o['LastModified'] > LAUNCH_UTC]

        # Estimate MB from result sizes
        total_mb = sum(o['Size'] for o in ok_results) // (1024 * 1024)
        print(f'[~{elapsed}m] state={state} | status={len(ok_statuses)}/30 | results={len(ok_results)}/30 ({total_mb} MB)', flush=True)

        if len(ok_results) > last_results:
            last_results = len(ok_results)
            if last_results == 1:
                r0 = ok_results[0]
                mins = (r0['LastModified'] - LAUNCH_UTC).total_seconds() / 60
                print(f'  *** First result at ~{mins:.1f}m: {r0["Key"].split("/")[-1]} ({r0["Size"]//1024} KB)', flush=True)

        if all_done_obj:
            print(f'  *** ALL_DONE! results={len(ok_results)}/30 ({total_mb} MB total)', flush=True)
            print('  Run: python sandbox/aws/download_results.py', flush=True)
            sys.exit(0)

        if state in ('terminated', 'stopped') and elapsed > 8:
            print(f'Instance stopped after {elapsed}m. results={len(ok_results)}', flush=True)
            sys.exit(1)

    except Exception as e:
        print(f'[~{elapsed}m] error: {e}', flush=True)

print('Timeout after ~105m', flush=True)
sys.exit(1)
