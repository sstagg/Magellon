import boto3, os, time, datetime, sys

os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
# Credentials from environment: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN

BUCKET  = 'magellon-gpu-eval-work'
SESSION = '24dec03a'
IID     = 'i-0a8228d6445fe8acb'
LAUNCH_UTC = datetime.datetime(2026, 5, 19, 23, 5, tzinfo=datetime.timezone.utc)

s3  = boto3.client('s3',  region_name='us-east-1')
ec2 = boto3.client('ec2', region_name='us-east-1')

def s3_objs(prefix):
    r = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
    return r.get('Contents', [])

def instance_state():
    r = ec2.describe_instances(InstanceIds=[IID])
    return r['Reservations'][0]['Instances'][0]['State']['Name']

print('Polling every 90s for v15 STARTED/ALL_DONE (up to 100 min)...', flush=True)

last_results = 0
for tick in range(66):  # ~100 min
    time.sleep(90)
    elapsed = int((datetime.datetime.now(datetime.timezone.utc) - LAUNCH_UTC).total_seconds() / 60)
    try:
        state   = instance_state()
        status  = [o['Key'] for o in s3_objs(f'{SESSION}/status/')]
        results = s3_objs(f'{SESSION}/results/')

        ok_results  = [o for o in results if o['LastModified'] > LAUNCH_UTC]
        ok_statuses = [o for o in s3_objs(f'{SESSION}/status/') if o['Key'].endswith('.status') and o['LastModified'] > LAUNCH_UTC]
        all_done_obj = [o for o in s3_objs(f'{SESSION}/status/') if 'ALL_DONE' in o['Key'] and o['LastModified'] > LAUNCH_UTC]

        print(f'[~{elapsed}m] state={state} | status={len(ok_statuses)} | results={len(ok_results)}', flush=True)

        if len(ok_results) > last_results:
            last_results = len(ok_results)
            # Show timing for first result
            if last_results == 1:
                r0 = ok_results[0]
                mins_to_first = (r0['LastModified'] - LAUNCH_UTC).total_seconds() / 60
                print(f'  *** First OK result at ~{mins_to_first:.1f}m: {r0["Key"].split("/")[-1]} ({r0["Size"]}B)', flush=True)

        if all_done_obj:
            run_log_ok = any('run.log' in o['Key'] for o in s3_objs(f'{SESSION}/status/'))
            print(f'  *** ALL_DONE! results={len(ok_results)} run_log={run_log_ok}', flush=True)
            sys.exit(0)

        if state in ('terminated', 'stopped'):
            if elapsed > 8:
                print(f'Instance stopped. status={status[:5]}', flush=True)
                sys.exit(1)
    except Exception as e:
        print(f'[~{elapsed}m] error: {e}', flush=True)

print('Timeout', flush=True)
sys.exit(1)
