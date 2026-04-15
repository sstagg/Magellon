"""Plugin broker harness — the boilerplate every plugin's ``main.py``
used to repeat (P5).

Each out-of-tree plugin previously hand-rolled the same loop:

  1. Connect to RabbitMQ.
  2. Declare an in-queue + an out-queue.
  3. For each delivery: decode JSON → ``TaskDto`` → ``InputT`` →
     ``plugin.run(input)`` → build ``TaskResultDto`` → publish to the
     out-queue → ack.
  4. NACK on exception (which used to mean "DLQ on every transient
     blip" — fixed by the P2 classifier).

That loop is identical across plugins. ``PluginBrokerRunner`` lifts
it into the SDK so a new plugin's ``main.py`` collapses to::

    from magellon_sdk.runner import PluginBrokerRunner

    runner = PluginBrokerRunner(
        plugin=MyPlugin(),
        settings=app_settings.rabbitmq_settings,
        in_queue="ctf_tasks_queue",
        out_queue="ctf_out_tasks_queue",
        result_factory=build_ctf_result,  # plugin's bespoke wrapper
    )
    runner.start_blocking()

The harness is sync (pika BlockingConnection) by deliberate choice —
matches the existing transport layer (see ``transport.rabbitmq_events``)
and the threading model the consumers run under. Async plugins are a
separate concern.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable, Optional

from pika.exceptions import ConnectionClosedByBroker

from magellon_sdk.base import PluginBase
from magellon_sdk.categories.contract import CategoryContract
from magellon_sdk.config_broker import ConfigSubscriber
from magellon_sdk.discovery import (
    Announce,
    DiscoveryPublisher,
    HeartbeatLoop,
)
from magellon_sdk.errors import AckAction, classify_exception
from magellon_sdk.models import TaskDto, TaskResultDto
from magellon_sdk.transport.rabbitmq import RabbitmqClient

logger = logging.getLogger(__name__)


# Plugins build the result DTO with their own wire-shape (every plugin
# fills in different output_data / meta_data / output_files). The
# harness only requires this signature; provenance is auto-injected
# from the plugin's manifest after the factory returns.
ResultFactory = Callable[[TaskDto, Any], TaskResultDto]


class PluginBrokerRunner:
    """Wire one ``PluginBase`` into a RabbitMQ task/result loop.

    Parameters
    ----------
    plugin :
        The plugin instance. ``plugin.run(input)`` is the callable the
        harness invokes per delivery; everything else (manifest,
        input_schema, get_info) is read for provenance + validation.
    settings :
        RMQ settings duck-typed object — needs ``HOST_NAME``,
        ``USER_NAME``, ``PASSWORD``, optional ``PORT`` / ``VIRTUAL_HOST``.
    in_queue :
        Queue name the plugin consumes ``TaskDto`` JSON from.
    out_queue :
        Queue name the harness publishes ``TaskResultDto`` JSON to.
    result_factory :
        Plugin-supplied callable that turns ``(task, plugin_output)``
        into a ``TaskResultDto``. The plugin owns its wire shape;
        the harness only stamps provenance afterwards.
    """

    def __init__(
        self,
        *,
        plugin: PluginBase,
        settings: Any,
        in_queue: str,
        out_queue: str,
        result_factory: ResultFactory,
        contract: Optional[CategoryContract] = None,
        heartbeat_interval_seconds: float = 15.0,
        enable_discovery: bool = True,
        enable_config: bool = True,
    ) -> None:
        self.plugin = plugin
        self.settings = settings
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.result_factory = result_factory
        # Discovery + heartbeat (P6). Optional so the harness still
        # works for plugins that haven't been migrated to declare a
        # contract yet — they just don't show up in the live registry.
        self.contract = contract
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.enable_discovery = enable_discovery and contract is not None
        # Dynamic config (P7). Same gate as discovery: needs a contract
        # to know which category subject to bind. The subscriber drains
        # between deliveries inside _process(), so a config push never
        # races a running execute().
        self.enable_config = enable_config and contract is not None
        self._stopping = threading.Event()
        self._heartbeat_loop: Optional[HeartbeatLoop] = None
        self._discovery_publisher: Optional[DiscoveryPublisher] = None
        self._config_subscriber: Optional[ConfigSubscriber] = None

    # ------------------------------------------------------------------
    # Per-message processing
    # ------------------------------------------------------------------

    def _process(self, body: bytes) -> bytes:
        """Decode → run → encode. Pure function for testability.

        Raises on any failure so the broker callback can route through
        :func:`classify_exception` and pick REQUEUE vs DLQ.
        """
        # Apply any pending config push *before* decoding the next task
        # so the plugin sees the new settings on the very next run.
        # Errors from a plugin's configure() must not poison the task —
        # log and continue with the previous config.
        self._apply_pending_config()

        text = body.decode("utf-8")
        task = TaskDto.model_validate_json(text)

        # Validate the task data against the plugin's declared input
        # schema before invoking. This is the same check P1's
        # CategoryContract does — running it here too keeps a malformed
        # task from reaching the plugin's bespoke logic.
        input_schema = self.plugin.input_schema()
        validated = input_schema.model_validate(task.data)

        plugin_output = self.plugin.run(validated)

        result = self.result_factory(task, plugin_output)
        self._stamp_provenance(result)

        return result.model_dump_json().encode("utf-8")

    def _stamp_provenance(self, result: TaskResultDto) -> None:
        """Fill in plugin_id / plugin_version from the manifest if the
        plugin's result_factory didn't already set them.

        Lets plugins be lazy ("the harness knows who I am") while still
        allowing a plugin to emit a different identity (e.g. an engine
        wrapper that runs gctf vs ctffind under one PluginBase)."""
        info = self.plugin.get_info()
        if result.plugin_id is None:
            result.plugin_id = info.name
        if result.plugin_version is None:
            result.plugin_version = info.version

    # ------------------------------------------------------------------
    # Broker loop
    # ------------------------------------------------------------------

    def _build_callback(self, client: RabbitmqClient):
        def _on_message(ch, method, properties, body):
            try:
                out_body = self._process(body)
                # Publish the result on the same channel; we're inside
                # the consumer thread, so it's safe to reuse.
                client.publish_message(out_body, self.out_queue)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            except Exception as exc:
                redeliveries = int(getattr(method, "redelivered", False))
                classification = classify_exception(
                    exc, redelivery_count=redeliveries
                )
                logger.warning(
                    "PluginBrokerRunner[%s]: %s → %s (%s)",
                    self.plugin.get_info().name,
                    type(exc).__name__,
                    classification.action.value,
                    classification.reason,
                )
                if classification.action is AckAction.REQUEUE:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                else:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        return _on_message

    def _start_discovery(self) -> None:
        """Publish the announce manifest + start the heartbeat loop.

        Idempotent: a reconnect re-runs the announce so a manager that
        came up after the plugin still picks it up. Heartbeat thread is
        only started once per process.
        """
        if not self.enable_discovery or self.contract is None:
            return
        if self._discovery_publisher is None:
            self._discovery_publisher = DiscoveryPublisher(self.settings)
        info = self.plugin.get_info()
        manifest = self.plugin.manifest()
        announce = Announce(
            plugin_id=info.name,
            plugin_version=info.version,
            category=self.contract.category.name.lower(),
            manifest=manifest,
        )
        try:
            self._discovery_publisher.announce(self.contract, announce)
        except Exception as exc:
            # Best-effort: a broker hiccup at announce time must not
            # take the consumer down. Heartbeats will eventually carry
            # the manager over.
            logger.warning("PluginBrokerRunner: announce failed: %s", exc)

        if self._heartbeat_loop is None:
            self._heartbeat_loop = HeartbeatLoop(
                publisher=self._discovery_publisher,
                contract=self.contract,
                plugin_id=info.name,
                plugin_version=info.version,
                instance_id=announce.instance_id,
                interval_seconds=self.heartbeat_interval_seconds,
            )
            self._heartbeat_loop.start()

    def _start_config_subscriber(self) -> None:
        """Spin up the config subscriber once per process."""
        if not self.enable_config or self.contract is None:
            return
        if self._config_subscriber is not None:
            return
        self._config_subscriber = ConfigSubscriber(
            self.settings, contract=self.contract
        )
        self._config_subscriber.start()

    def _apply_pending_config(self) -> None:
        """Drain the subscriber buffer and hand it to the plugin.

        Called from :meth:`_process` between deliveries — never while
        ``execute()`` is running. A bad ``configure()`` call must not
        derail the task loop, so exceptions are caught and logged.
        """
        if self._config_subscriber is None:
            return
        pending = self._config_subscriber.take_pending()
        if not pending:
            return
        try:
            self.plugin.configure(pending)
            logger.info(
                "PluginBrokerRunner[%s]: applied config update (%d keys)",
                self.plugin.get_info().name,
                len(pending),
            )
        except Exception as exc:
            logger.warning(
                "PluginBrokerRunner[%s]: configure() raised %s — keeping previous config",
                self.plugin.get_info().name,
                exc,
            )

    def start_blocking(self) -> None:
        """Run the consume loop on the calling thread. Reconnects on
        broker bounce. Returns when ``stop()`` is called."""
        while not self._stopping.is_set():
            client = RabbitmqClient(self.settings)
            try:
                client.connect()
                client.declare_queue(self.in_queue)
                client.declare_queue(self.out_queue)
                client.consume(self.in_queue, self._build_callback(client))
                self._start_discovery()
                self._start_config_subscriber()
                logger.info(
                    "PluginBrokerRunner[%s]: consuming %s, publishing %s",
                    self.plugin.get_info().name,
                    self.in_queue,
                    self.out_queue,
                )
                client.start_consuming()
            except KeyboardInterrupt:
                logger.info("PluginBrokerRunner: interrupted")
                break
            except ConnectionClosedByBroker:
                logger.warning(
                    "PluginBrokerRunner: broker closed connection — reconnecting in 5s"
                )
                time.sleep(5)
            except Exception as exc:
                logger.error(
                    "PluginBrokerRunner: loop crashed (%s) — reconnecting in 5s", exc
                )
                time.sleep(5)
            finally:
                client.close_connection()

    def stop(self) -> None:
        self._stopping.set()
        if self._heartbeat_loop is not None:
            self._heartbeat_loop.stop()
        if self._discovery_publisher is not None:
            self._discovery_publisher.close()
        if self._config_subscriber is not None:
            self._config_subscriber.stop()


__all__ = ["PluginBrokerRunner", "ResultFactory"]
