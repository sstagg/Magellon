"""
Download v15 MotionCor2 results from S3 and extract into fao/ directory.

Usage:
  python sandbox/aws/download_results.py
"""
import boto3, os, tarfile, datetime, io

os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

BUCKET      = 'magellon-gpu-eval-work'
SESSION     = '24dec03a'
LAUNCH_UTC  = datetime.datetime(2026, 5, 19, 23, 5, tzinfo=datetime.timezone.utc)
LOCAL_FAO   = r'C:\magellon\gpfs\24dec03a\home\fao'

s3 = boto3.client('s3', region_name='us-east-1')

def list_v15_results():
    r = s3.list_objects_v2(Bucket=BUCKET, Prefix=f'{SESSION}/results/')
    objects = r.get('Contents', [])
    return [o for o in objects if o['LastModified'] > LAUNCH_UTC and o['Key'].endswith('.tar.gz')]

def frame_stem(key):
    # e.g. 24dec03a/results/20241203_54480_integrated_movie.mrc.tar.gz
    fname = key.split('/')[-1]          # 20241203_54480_integrated_movie.mrc.tar.gz
    return fname[:-7]                   # strip .tar.gz → 20241203_54480_integrated_movie.mrc

results = list_v15_results()
print(f'Found {len(results)} v15 result tarballs in S3')

ok = 0
for obj in sorted(results, key=lambda o: o['Key']):
    key   = obj['Key']
    size  = obj['Size']
    stem  = frame_stem(key)
    outdir = os.path.join(LOCAL_FAO, stem)   # stem already ends in .mrc
    os.makedirs(outdir, exist_ok=True)

    print(f'  [{ok+1}/{len(results)}] {stem}  ({size//1024//1024} MB)', end=' ', flush=True)

    body = s3.get_object(Bucket=BUCKET, Key=key)['Body'].read()
    with tarfile.open(fileobj=io.BytesIO(body), mode='r:gz') as tf:
        members = tf.getmembers()
        tf.extractall(path=outdir)
    files = os.listdir(outdir)
    print(f'-> extracted {len(members)} files: {files}')
    ok += 1

print(f'\nDone. {ok}/{len(results)} frames extracted to {LOCAL_FAO}')
