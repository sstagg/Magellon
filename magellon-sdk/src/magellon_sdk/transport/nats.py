"""NATS JetStream publisher/consumer for Magellon inter-service events.

This replaces the copy-paste pair under
``CoreService/support/events/{publisher,subscriber}.py`` where stream
name, subject, and broker URL were hardcoded. All three are now
constructor parameters so tests can use isolated streams and so the
same classes serve multiple event pipelines (e.g. job progress vs.
plugin lifecycle).

Payloads are carried as :class:`magellon_sdk.envelope.Envelope` —
CloudEvents 1.0-compliant — so everything that crosses the wire has a
uniform ``id``/``source``/``type``/``subject``/``time`` header.

Example:

    from magellon_sdk.envelope import Envelope
    from magellon_sdk.transport.nats import NatsPublisher, NatsConsumer

    pub = NatsPublisher("nats://127.0.0.1:4222", stream="EVENTS", subjects=["events.*"])
    await pub.connect()
    await pub.publish("events.ctf.completed", Envelope.wrap(
        source="magellon/plugins/ctf", type="magellon.step.completed",
        subject="magellon.job.abc.step.ctf", data={"defocus": 1.2},
    ))
    await pub.close()
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Iterable, Optional

import nats
from nats.errors import Error as NatsError

from magellon_sdk.envelope import Envelope

logger = logging.getLogger(__name__)

EnvelopeCallback = Callable[[Envelope[Any]], Awaitable[None]]


class NatsPublisher:
    """Config-driven JetStream publisher.

    Idempotent ``connect()`` — creates the stream if it doesn't exist,
    silently accepts "stream name already in use". Callers publish
    :class:`Envelope` instances and the publisher serializes them to
    JSON + sets CloudEvents headers.
    """

    def __init__(
        self,
        broker_url: str,
        *,
        stream: str,
        subjects: Iterable[str],
        connect_timeout: float = 3.0,
    ) -> None:
        self.broker_url = broker_url
        self.stream = stream
        self.subjects = list(subjects)
        self.connect_timeout = connect_timeout
        self.nc: Any = None
        self.js: Any = None

    async def connect(self) -> None:
        if self.nc:
            return
        # Hard-bound the whole connect path. nats.connect() is usually fast
        # but js.add_stream() will wait indefinitely for a JetStream RPC
        # reply when the broker is up but JetStream isn't enabled — leaving
        # callers (publisher init, step-event reporter) hanging forever.
        # asyncio.wait_for cancels both legs cleanly on deadline.
        try:
            await asyncio.wait_for(self._connect_inner(), timeout=self.connect_timeout)
        except asyncio.TimeoutError as exc:
            # Surface as a generic Exception so make_step_publisher's
            # broad-except falls back to RMQ-only.
            raise RuntimeError(
                f"NATS connect timed out after {self.connect_timeout}s "
                f"(broker reachable? JetStream enabled?)"
            ) from exc

    async def _connect_inner(self) -> None:
        self.nc = await nats.connect(self.broker_url)
        self.js = self.nc.jetstream()
        try:
            await self.js.add_stream(name=self.stream, subjects=self.subjects)
            logger.info("NATS stream %r created", self.stream)
        except NatsError as e:
            msg = str(e)
            # Two benign "already exists" shapes from the broker:
            #   * same stream name re-declared with matching config
            #   * a *different* stream already owns one of our subjects
            # Both mean: the JetStream we want to publish to already
            # exists. Either way the publish path works, so swallow
            # rather than poisoning the whole step-event publisher.
            if "stream name already in use" in msg or "subjects overlap" in msg:
                logger.debug("NATS stream %r already present (%s)", self.stream, msg)
            else:
                raise

    async def publish(self, subject: str, envelope: Envelope[Any]) -> Any:
        if not self.js:
            raise RuntimeError("NatsPublisher.connect() must be awaited before publish()")
        body = envelope.model_dump_json().encode("utf-8")
        headers = {
            "ce-specversion": envelope.specversion,
            "ce-id": envelope.id,
            "ce-source": envelope.source,
            "ce-type": envelope.type,
            "content-type": envelope.datacontenttype,
        }
        if envelope.subject:
            headers["ce-subject"] = envelope.subject
        return await self.js.publish(subject, body, headers=headers)

    async def close(self) -> None:
        if self.nc:
            await self.nc.close()
            self.nc = None
            self.js = None


class NatsConsumer:
    """Config-driven JetStream pull-subscriber.

    ``connect()`` returns ``True`` on success and ``False`` if the
    target stream does not yet exist (so callers can back off and
    retry, matching the FastAPI startup-hook pattern). All other
    JetStream errors propagate.
    """

    def __init__(
        self,
        broker_url: str,
        *,
        stream: str,
        subject: str,
        durable_name: str,
        fetch_batch: int = 10,
        fetch_timeout: float = 1.0,
        ensure_stream: bool = True,
        connect_timeout: float = 2.0,
        max_reconnect_attempts: int = 2,
    ) -> None:
        self.broker_url = broker_url
        self.stream = stream
        self.subject = subject
        self.durable_name = durable_name
        self.fetch_batch = fetch_batch
        self.fetch_timeout = fetch_timeout
        self.ensure_stream = ensure_stream
        self.connect_timeout = connect_timeout
        self.max_reconnect_attempts = max_reconnect_attempts
        self.nc: Any = None
        self.js: Any = None
        self.sub: Any = None
        self.running: bool = False
        self._task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        if self.nc:
            return True

        # Mute nats.aio.client BEFORE the call. The library logs every
        # failed reconnect attempt at ERROR with a full stack trace; we
        # don't want that whether the connect succeeds or fails. We
        # restore on success so genuine post-connect errors still show.
        nats_logger = logging.getLogger("nats.aio.client")
        prior_level = nats_logger.level
        nats_logger.setLevel(logging.CRITICAL)
        try:
            self.nc = await nats.connect(
                self.broker_url,
                connect_timeout=self.connect_timeout,
                max_reconnect_attempts=0,
                allow_reconnect=False,
            )
        except Exception as e:
            logger.info(
                "NATS broker %s not reachable (%s) — consumer will not start",
                self.broker_url, e,
            )
            return False
        else:
            nats_logger.setLevel(prior_level or logging.WARNING)
        self.js = self.nc.jetstream()

        try:
            await self.js.stream_info(self.stream)
        except NatsError:
            # Stream missing. Either we own it (ensure_stream=True) and
            # create it ourselves so a publisher arriving later just hits
            # the idempotent "stream name already in use" path; or we
            # back off and let the caller retry. The default (True)
            # eliminates the historical boot-order race where the backend
            # gave up because plugins hadn't published yet.
            if not self.ensure_stream:
                logger.info(
                    "NATS stream %r not yet present — consumer will wait", self.stream
                )
                return False
            try:
                await self.js.add_stream(name=self.stream, subjects=[self.subject])
                logger.info(
                    "NATS stream %r auto-created by consumer (subjects=%s)",
                    self.stream, [self.subject],
                )
            except NatsError as e:
                # Race: a publisher created it between our check and add.
                # Benign — proceed to consumer attach.
                if "stream name already in use" not in str(e):
                    logger.warning(
                        "NATS stream %r ensure failed: %s — consumer will wait",
                        self.stream, e,
                    )
                    return False

        try:
            await self.js.add_consumer(
                self.stream,
                durable_name=self.durable_name,
                ack_policy="explicit",
            )
        except NatsError as e:
            # add_consumer on an existing durable is a benign error —
            # a fresh consumer on the same name just adopts it.
            logger.debug("add_consumer %r: %s", self.durable_name, e)
        return True

    async def subscribe(self, callback: EnvelopeCallback) -> None:
        if not self.js:
            raise RuntimeError("NatsConsumer.connect() must be awaited before subscribe()")
        self.sub = await self.js.pull_subscribe(self.subject, durable=self.durable_name)
        self.running = True
        self._task = asyncio.create_task(self._loop(callback))

    async def _loop(self, callback: EnvelopeCallback) -> None:
        while self.running:
            try:
                msgs = await self.sub.fetch(batch=self.fetch_batch, timeout=self.fetch_timeout)
            except asyncio.TimeoutError:
                # fetch already blocked for fetch_timeout — no extra sleep.
                continue
            except Exception as e:  # noqa: BLE001
                logger.warning("NatsConsumer fetch error: %s", e)
                await asyncio.sleep(1)
                continue

            for msg in msgs:
                try:
                    envelope = Envelope.model_validate_json(msg.data)
                    await callback(envelope)
                    await msg.ack()
                except Exception as e:  # noqa: BLE001
                    logger.exception("NatsConsumer callback failed: %s", e)
                    await msg.nak()

    async def close(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

        if self.sub:
            try:
                await self.sub.unsubscribe()
            except Exception:
                pass
            self.sub = None

        if self.nc:
            await self.nc.close()
            self.nc = None
            self.js = None


__all__ = ["EnvelopeCallback", "NatsConsumer", "NatsPublisher"]
