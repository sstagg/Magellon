# magellon-sdk changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Version pattern follows SemVer as defined in `CONTRACT.md` §4.

---

## [Unreleased]

(no changes yet)

---

## 1.0.0 — 2026-04-17

First frozen public contract. See `CONTRACT.md` for the scope of
what's covered. Everything listed there is promised stable within
the 1.x.y major.

### Changed — breaking, pre-1.0 cleanup (acceptable because the SDK
### had not been used in production)

- **`TaskBase.sesson_id` / `sesson_name` → `session_id` / `session_name`.**
  Fixed a typo that had propagated through 16 files. Every caller
  updated in the same commit; no compatibility alias kept.
- **`CryoEmMotionCorTaskData.outputFile` dropped.** Redundant with
  the canonical `OutMrc` (which mirrors the MotionCor3 binary's
  `-OutMrc` CLI flag and is the name the binary actually reads).
  Plugin callers consolidated on `OutMrc`.
- **Top-level `magellon_sdk.__init__.py` re-exports broadened.**
  `PluginBrokerRunner`, `TaskDto`, `TaskResultDto`, `PluginInfo`,
  `PluginManifest`, `install_rmq_bus`, `install_inmemory_bus`,
  `install_mock_bus` are now importable from `magellon_sdk` directly.
  Previous short list (`PluginBase`, `Envelope`, `NullReporter`,
  `ProgressReporter`, `JobCancelledError`) is retained.

### Added

- `magellon-sdk/CONTRACT.md` — authoritative public-surface map,
  SemVer policy, deprecation policy. Commit `bfa8845`.
- `magellon-sdk/CHANGELOG.md` — this file.
- JSON Schemas (`input_schema` / `output_schema`) in `PluginManifest`
  via `PluginBase.manifest()`. Best-effort emit from the plugin's
  Pydantic input/output classes. Unlocks UI form-rendering and
  upload-validation for the hub. Commit `0ec2cb2`.
- `__all__` added to `magellon_sdk/transport/rabbitmq.py` (explicit
  public surface is `RabbitmqClient` only).
- Module docstring on `magellon_sdk/discovery.py` clarifying that
  `DiscoveryPublisher` / `HeartbeatLoop` are harness internals —
  plugin authors run a `PluginBrokerRunner` which wires them up.

### Fixed

- `CtfTaskData.outputFile`: default was `"ouput.mrc"` (typo). Now
  `"output.mrc"`. Commit `7bc0d47`.
- `NatsPublisher.connect`: added `connect_timeout` parameter
  (default 3s). Prevents indefinite hang on `js.add_stream` when a
  NATS broker is reachable but JetStream isn't enabled — previously
  stalled plugin boot. Commit `07f8497`.
- `_RmqAsyncAdapter.publish`: strips `magellon.` prefix when
  translating a NATS subject to an RMQ routing key. Without this,
  step events published from plugins landed on `magellon.events` but
  matched no binding. Silent data loss. Commit `07f8497`.
- `RmqBinder.publish_task`: reconnect once on stale-connection
  errors (`AMQPConnectionError` / `ChannelError` / `StreamLostError`).
  Pika's `BlockingConnection` doesn't auto-reconnect; an idle drop
  used to mean every subsequent publish failed until binder restart.
  Commit `47339f3`.

### Migration notes (if you built against 0.1.0)

- Rename `sesson_*` → `session_*` in your plugin code. `grep -rn
  sesson_ . --include="*.py"` finds every hit.
- `CryoEmMotionCorTaskData.outputFile` → `OutMrc` (the field was
  never sent to the binary; it was parallel to `OutMrc`). All
  existing MotionCor logic already uses `OutMrc` internally.
- Pin `magellon-sdk>=1.0,<2.0` in your plugin's requirements.
- The bundled wheel filename is now `magellon_sdk-1.0.0-py3-none-any.whl`.
  Dockerfiles that `COPY` the wheel need the filename updated.

---

## 0.1.0 — 2026-03-xx

Initial SDK. Bus Protocol + binders (MB1–MB2), discovery harness,
step events, `PluginBase` contract, `PluginBrokerRunner`.
Reference plugins: FFT, CTF, MotionCor. No public contract
guarantees.
