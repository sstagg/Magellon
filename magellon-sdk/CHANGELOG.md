# magellon-sdk changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Version pattern follows SemVer as defined in `CONTRACT.md` §4.

---

## [Unreleased]

### Pending before 1.0.0

See `CONTRACT.md` §6 for the decisions that gate the 1.0.0 tag.

### Added

- JSON Schemas (`input_schema` / `output_schema`) emitted in
  :class:`PluginManifest` via :meth:`PluginBase.manifest`. Unlocks
  form-rendering in the UI, schema-compat checks between plugin
  versions, and upload validation once the plugin hub lands.
  Commit `0ec2cb2`.

### Fixed

- :class:`CtfTaskData`: ``outputFile`` default was ``"ouput.mrc"``
  (typo). Now ``"output.mrc"``. Commit `7bc0d47`.

- :class:`NatsPublisher.connect`: added ``connect_timeout`` parameter
  (default 3s). Previously, a reachable NATS broker without JetStream
  would hang the publisher's ``connect()`` indefinitely on
  ``js.add_stream``, stalling plugin boot. Commit `07f8497`.

- :class:`_RmqAsyncAdapter.publish`: strips ``magellon.`` prefix when
  translating a NATS subject to an RMQ routing key. Without this,
  step events published from plugins landed on the ``magellon.events``
  exchange but matched no binding (``job.*.step.*`` bindings require
  keys like ``job.<id>.step.<step>``, not
  ``magellon.job.<id>.step.<step>``). Silent data loss. Commit
  `07f8497`.

- :class:`RmqBinder.publish_task`: reconnect once on stale-connection
  errors (``AMQPConnectionError`` / ``ChannelError`` /
  ``StreamLostError``). Pika's ``BlockingConnection`` doesn't
  auto-reconnect, so an idle drop (broker restart, network blip)
  used to mean every subsequent publish failed until the binder
  host restarted. Commit `47339f3`.

---

## 1.0.0 — not yet tagged

**Target:** first frozen public contract. See `CONTRACT.md` for what's
covered. Must resolve all items in `CONTRACT.md` §6 before tagging.

---

## 0.1.0 — 2026-03-xx

Initial SDK. Bus Protocol + binders (MB1–MB2), discovery harness,
step events, `PluginBase` contract, `PluginBrokerRunner`.
Reference plugins: FFT, CTF, MotionCor. No public contract
guarantees.
