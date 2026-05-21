"""
Download v16 MotionCor2 results from S3 and extract into fao/ directory.

v16 tarballs contain: STEM_BASE.mrc, STEM_BASE_DW.mrc, *-Patch-Patch.log,
*-Patch-Full.log, *-Patch-Frame.log.  Each tarball is extracted into a
per-stem subdirectory so all associated files stay together.

Usage:
  python sandbox/aws/download_results.py
"""
import boto3, os, tarfile, datetime, io

os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

BUCKET      = 'magellon-gpu-eval-work'
SESSION     = '24dec03a'
LAUNCH_UTC  = datetime.datetime(2026, 5, 21, 8, 0, tzinfo=datetime.timezone.utc)
LOCAL_FAO   = r'C:\magellon\gpfs\home\24dec03a\fao'

s3 = boto3.client('s3', region_name='us-east-1')

def list_v16_results():
    r = s3.list_objects_v2(Bucket=BUCKET, Prefix=f'{SESSION}/results/')
    objects = r.get('Contents', [])
    return [o for o in objects if o['LastModified'] > LAUNCH_UTC and o['Key'].endswith('.tar.gz')]

def frame_stem(key):
    # e.g. 24dec03a/results/20241203_54480_integrated_movie.mrc.tar.gz
    fname = key.split('/')[-1]          # 20241203_54480_integrated_movie.mrc.tar.gz
    stem  = fname[:-7]                  # strip .tar.gz -> 20241203_54480_integrated_movie.mrc
    return stem[:-4] if stem.endswith('.mrc') else stem  # strip inner .mrc -> STEM_BASE

results = list_v16_results()
print(f'Found {len(results)} v16 result tarballs in S3')

ok = 0
for obj in sorted(results, key=lambda o: o['Key']):
    key      = obj['Key']
    size     = obj['Size']
    stem     = frame_stem(key)
    outdir   = os.path.join(LOCAL_FAO, stem)
    os.makedirs(outdir, exist_ok=True)

    print(f'  [{ok+1}/{len(results)}] {stem}  ({size//1024} KB)', end=' ', flush=True)

    body = s3.get_object(Bucket=BUCKET, Key=key)['Body'].read()
    with tarfile.open(fileobj=io.BytesIO(body), mode='r:gz') as tf:
        members = tf.getmembers()
        tf.extractall(path=outdir)
    files = os.listdir(outdir)
    dw = [f for f in files if '_DW' in f]
    logs = [f for f in files if f.endswith('.log')]
    print(f'-> {len(members)} files  DW={len(dw)}  logs={len(logs)}  [{", ".join(files[:4])}{"..." if len(files)>4 else ""}]')
    ok += 1

print(f'\nDone. {ok}/{len(results)} frames extracted to {LOCAL_FAO}')
if ok > 0:
    print('\nPer-frame directory layout:')
    for d in sorted(os.listdir(LOCAL_FAO))[:3]:
        dpath = os.path.join(LOCAL_FAO, d)
        if os.path.isdir(dpath):
            contents = os.listdir(dpath)
            print(f'  {d}/  -> {contents}')
