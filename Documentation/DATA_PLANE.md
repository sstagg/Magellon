# Magellon — Data Plane: Shared Filesystem

**Status:** Canonical architectural decision as of 2026-04-21.
**Audience:** Operators, plugin developers, deployment engineers.
**Companion docs:** `ARCHITECTURE_PRINCIPLES.md` §1, `CURRENT_ARCHITECTURE.md`, `MESSAGE_BUS_SPEC.md`.

---

## 1. The decision

Magellon has two transport planes:

- **Control plane — the MessageBus** (`magellon_sdk.bus`). Carries
  task dispatch, results metadata, events, discovery, configuration,
  cancellation. Small payloads (≤ 10 KB per envelope, typically much
  less). Durable, versioned, observable.
- **Data plane — a shared POSIX filesystem** mounted at
  `MAGELLON_HOME_DIR` on CoreService and every plugin worker.
  Carries raw and derived image data: MRC files, motion-corrected
  outputs, CTF star files, thumbnails, FFTs. Large payloads
  (MB per micrograph, GB per movie, TB per session).

Metadata flows on the bus. Bytes flow on the filesystem. The bus
carries path references to files the data plane makes real.

---

## 2. Why this split

**Cryo-EM payload sizes forbid the alternative.** A single K3
micrograph is 10–20 MB. A raw movie is 1–10 GB. A typical session
produces thousands of these. Routing them through the bus would:

- Blow past CloudEvents envelope guidance (≤ 256 KB) and every
  broker's practical message-size limit.
- Defeat broker durability — JetStream retention walls, RMQ lazy-
  queue memory pressure — long before a session finishes.
- Double the I/O: every byte would be written to disk by the
  plugin, serialized, published, received, deserialized, and
  written *again* by CoreService.

**The domain already assumes it.** CryoSPARC, Relion, and Scipion
all assume a shared scratch filesystem visible to every worker.
HPC clusters run cryo-EM on GPFS, Lustre, BeeGFS, or CephFS as a
matter of course. Fighting this pattern would buy nothing and
cost deployment compatibility.

**The bus stays small and fast.** Keeping large binary data off
the bus means the bus stays durable, low-latency, and cheaply
instrumented. The control plane serves its actual purpose.

---

## 3. What flows on each plane

### Control plane (bus)

| Carried | Example | Typical size |
|---|---|---|
| Task dispatch | `TaskDto` with `image_path: str` | 1–4 KB |
| Task result | `TaskResultDto` with output paths + metadata | 1–8 KB |
| Step events | `magellon.step.progress` envelopes | < 1 KB |
| Discovery | Announce / heartbeat | < 1 KB |
| Config push | `magellon.plugins.config.<cat>` updates | 1–4 KB |
| Cancellation | Operator intents | < 1 KB |

### Data plane (filesystem)

| Carried | Example path | Typical size |
|---|---|---|
| Raw frames | `$MAGELLON_HOME_DIR/<session>/frames/<image>.mrc` | 10 MB – 10 GB |
| Motion-corrected | `$MAGELLON_HOME_DIR/<session>/motioncor/<image>_aligned.mrc` | 10–100 MB |
| CTF outputs | `$MAGELLON_HOME_DIR/<session>/ctf/<image>.star` | < 1 MB (many files) |
| Thumbnails / PNGs | `$MAGELLON_HOME_DIR/<session>/thumbnails/<image>.png` | 100 KB – 1 MB |
| FFTs | `$MAGELLON_HOME_DIR/<session>/fft/<image>_fft.png` | 100 KB – 1 MB |

The `<session>/<category>/<image>` layout convention is enforced
by `CoreService/services/task_output_processor.py::_get_destination_dir`.
Plugins that deviate break the projection.

---

## 4. Mount requirement

**Single namespace, visible to all.** CoreService and every plugin
worker — in-process, subprocess, or containerized — must see the
same path resolve to the same file. If plugin A writes
`$MAGELLON_HOME_DIR/<session>/foo.mrc` and plugin B cannot read
that path, the deployment is broken.

This is a deployment prerequisite, not a Magellon bug. Operators
own provisioning the shared filesystem; the platform assumes it.

---

## 5. Acceptable implementations

| Deployment | Backing | Notes |
|---|---|---|
| HPC / on-prem cluster | GPFS, Lustre, BeeGFS, CephFS | Recommended — designed for exactly this workload. |
| On-prem Kubernetes | CephFS, NFS with RWX PV | PV `accessModes` must include `ReadWriteMany`. |
| Single-node `docker-compose` | Docker bind mount | Dev default; every service mounts the same host dir. |
| AWS | EFS | `ReadWriteMany`; provisioned throughput sized per session. |
| GCP | Filestore | Basic for dev, HDD for small sessions, SSD for prod. |
| Azure | Azure Files (NFS protocol) | SMB works but POSIX semantics are cleaner. |

**Smaller scales.** A single NFS export between two hosts is a
valid entry point. Not recommended past ~2 plugin replicas — NFSv3
locking behaviour and `rename` atomicity become fragile under
concurrent writes.

---

## 6. Plugin obligations

Plugins using the data plane must:

1. **Read and write only under `$MAGELLON_HOME_DIR`.** Never use
   `/tmp` for cross-plugin artifacts — it's not shared.
2. **Write to session-scoped subdirectories.**
   `<session>/<category>/<image>` is the layout the result
   projector assumes.
3. **Return file paths, not bytes, in `TaskResultDto`.** The
   result processor moves files based on the paths the plugin
   reports.
4. **Handle partial writes atomically.** Write to a temp name
   under the session dir, then `os.rename` to the final name —
   `rename` within one filesystem is atomic on POSIX.
5. **Tolerate eventual consistency on some backends.** EFS metadata
   ops are strongly consistent; NFSv3 `readdir` after `rename`
   may lag. If a plugin needs to see another plugin's output,
   sequence that dependency via the bus, not via filesystem
   polling.

---

## 7. What this forecloses on

Deliberately out of scope:

- **Object-storage-only deployments** (S3, GCS, Azure Blob without
  a filesystem gateway). A Magellon plugin cannot assume S3
  semantics — no `rename`, no atomic listings, eventual consistency
  on reads after writes. If an S3-only target becomes a product
  requirement, it's a separate architectural track, not a quick
  adapter.
- **Serverless cloud GPU** (RunPod, Lambda, Cloud Run Jobs)
  *without* a persistent attached filesystem volume. These
  platforms work only if they can mount the shared filesystem.
  Otherwise the plugin has no way to produce output CoreService
  can see.
- **Byte-addressable data on the bus.** A future "small images fit
  in the envelope" optimisation is not supported. Keep the plane
  separation strict.

These are not regrets. They are the cost of a simple, fast, domain-
appropriate architecture. Operators needing one of the above should
treat Magellon's deployment requirements as a selection criterion.

---

## 8. Operator surface

Per `ARCHITECTURE_PRINCIPLES.md` §7, the data plane answers three
questions:

- **Observe.** `df -h $MAGELLON_HOME_DIR` gives capacity; Prometheus
  node_exporter's filesystem collector tracks free bytes, inode
  usage, and write latency.
- **Drain.** Session cleanup is currently manual
  (`rm -r $MAGELLON_HOME_DIR/<session>`). A retention policy per
  session is open work, tracked under Track B if it graduates.
- **Recover.** A full data plane is recoverable from the raw-frame
  backup (customer-owned). CoreService's MySQL state lets the
  platform re-run any step whose inputs survive.

---

## 9. Open questions

Deferred until evidence justifies them:

1. **Per-session quotas.** One rogue session can fill the plane for
   everyone. GPFS and Lustre support per-fileset quotas; NFS via
   `xfs_quota`. Do we want this platform-enforced? Not yet — no
   incident has forced it.
2. **Archival tier.** Sessions older than N days could move to
   cheaper storage. Design space is large (HSM, S3 IA, glacier);
   no customer has asked.
3. **Checksums on result files.** A corrupted output propagates
   silently today. A hash in `TaskResultDto` is cheap; worth doing
   if plugin crashes ever produce half-written MRCs — no evidence
   yet.

---

## 10. What to read next

- `ARCHITECTURE_PRINCIPLES.md` — the canonical rule-set this doc
  implements for the data plane.
- `CoreService/services/task_output_processor.py` — the live code
  that reads and moves files under `MAGELLON_HOME_DIR`.
- `Docker/docker-compose.yml` — the reference bind-mount layout
  for dev; every plugin service gets `/magellon:/magellon:rw`.
