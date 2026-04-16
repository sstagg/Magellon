# Upload Pipeline — S3 + Presigned URLs + Trigger Lambda

Users upload MotionCor2 input movies directly to S3, which triggers a Batch job, and the user gets a presigned download URL back for the output.

**Bucket stays private.** Only way in/out is presigned URLs minted by our Lambdas. "Block Public Access" is on.

## Architecture

```
Browser              Lambda URL          S3 work bucket         Batch
  │ POST /upload-url    │                   │                     │
  │──────────────────►│                   │                     │
  │ {upload_url, job_id}                    │                     │
  │◄──────────────────│                   │                     │
  │                   │                   │                     │
  │ PUT (movie.tif) ────────────────────►│  (object created)    │
  │                                       │─── S3 event ────────►│
  │                                       │                     │ submits job
  │                                       │                     ▼
  │                                       │◄── .mrc output ── container
  │                                       │                     │
  │ GET /download-url/{job_id}             │                     │
  │──────────────────►│                   │                     │
  │ {download_urls}     │                   │                     │
  │◄──────────────────│                   │                     │
```

## Endpoints (Lambda Function URLs)

| Method/Path | Purpose | Returns |
|---|---|---|
| `POST /` with `{"action":"mint_upload","filename":"x.tif"}` | Get PUT URL | `{job_id, upload_url, expires_in}` |
| `POST /` with `{"action":"status","job_id":"..."}` | Check job status | `{status, outputs?}` |
| `POST /` with `{"action":"mint_download","job_id":"..."}` | Get GET URLs for outputs | `{download_urls:[...]}` |

Uses a single Lambda with action-based routing — keeps deploy simple.

## Safety limits (in handler code)

- Presigned PUT URL valid 1h
- Presigned GET URL valid 1h
- S3 lifecycle deletes everything after 7 days (set in `common/03-setup-buckets.sh`)
- Max upload size: not enforced on URL but downstream Batch job has a 2h timeout
- Anyone who can hit the Lambda URL can mint a PUT URL — it's behind an API key for the demo (see `deploy.sh`)

## Files

```
handlers/
  upload_api.py     # Single Lambda: mint_upload, status, mint_download actions
  on_upload.py      # S3 event → Batch job submission
web/
  index.html        # Browser demo: pick file, upload, poll, download
deploy.sh           # Creates Lambda fns, Function URL, S3 event notification
teardown.sh         # Deletes everything (keeps bucket — use common/cleanup)
```

## Run

```bash
source ../common/activate.sh
# Assumes common/00-setup-iam.sh + common/03-setup-buckets.sh + test-1 Batch resources exist
./deploy.sh
# Output includes the Lambda Function URL and the API key

# Edit web/index.html's API_URL + API_KEY, then open in browser.
```
