"""Plugin broker harness — wires a :class:`PluginBase` into the bus.

Pre-MB4.1 the runner owned its own :class:`RabbitmqClient` and drove
pika's blocking consume loop directly. Post-MB4.1 task I/O (consume
incoming tasks, publish results) goes through the MessageBus: the
caller-supplied ``in_queue`` / ``out_queue`` strings become
:class:`TaskRoute` / :class:`TaskResultRoute` ``.named(...)`` routes,
and the binder behind the bus (RMQ in production, InMemory in tests)
handles the transport.

Discovery (announce + heartbeat) and config subscription still run
against a direct pika connection — those migrate to ``bus.events`` in
MB5. For now the runner needs both an RMQ-compatible ``settings``
object (for discovery/config) and a bus (for task I/O).

The constructor signature is unchanged for backward compatibility —
every existing plugin's ``main.py`` keeps working. New callers that
want to pass a specific bus (tests, in-memory runs) can use the new
``bus=`` keyword; otherwise the runner pulls it from :func:`get_bus`.

A new plugin's ``main.py`` now looks like::

    from magellon_sdk.bus.bootstrap import install_rmq_bus
    from magellon_sdk.runner import PluginBrokerRunner

    install_rmq_bus(app_settings.rabbitmq_settings)
    runner = PluginBrokerRunner(
        plugin=MyPlugin(),
        settings=app_settings.rabbitmq_settings,  # discovery + config
        in_queue="ctf_tasks_queue",
        out_queue="ctf_out_tasks_queue",
        result_factory=build_ctf_result,
    )
    runner.start_blocking()

Per-message handler: :meth:`_handle_task` receives an Envelope from
the bus, validates the data against the plugin's ``input_schema``,
runs the plugin, stamps provenance, and publishes the result via
``bus.tasks.send``. Raising routes through the standard
``classify_exception`` taxonomy — same REQUEUE / DLQ semantics the
binder enforces.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Optional

from magellon_sdk.base import PluginBase
from magellon_sdk.bus._facade import get_bus
from magellon_sdk.bus.interfaces import ConsumerHandle, MessageBus
from magellon_sdk.bus.routes import TaskResultRoute, TaskRoute
from magellon_sdk.categories.contract import CategoryContract
from magellon_sdk.config_broker import ConfigSubscriber
from magellon_sdk.discovery import DiscoveryPublisher, HeartbeatLoop
from magellon_sdk.envelope import Envelope
from magellon_sdk.models import FAILED, TaskDto, TaskResultDto
from magellon_sdk.progress import JobCancelledError
from magellon_sdk.runner.lifecycle import start_config_subscriber, start_discovery

logger = logging.getLogger(__name__)


# Plugins build the result DTO with their own wire-shape (every plugin
# fills in different output_data / meta_data / output_files). The
# harness only requires this signature; provenance is auto-injected
# from the plugin's manifest after the factory returns.
ResultFactory = Callable[[TaskDto, Any], TaskResultDto]


class PluginBrokerRunner:
    """Wire one ``PluginBase`` into the bus's task loop.

    Parameters
    ----------
    plugin :
        The plugin instance. ``plugin.run(input)`` is the callable the
        harness invokes per delivery; everything else (manifest,
        input_schema, get_info) is read for provenance + validation.
    settings :
        RMQ settings duck-typed object — needs ``HOST_NAME``,
        ``USER_NAME``, ``PASSWORD``, optional ``PORT`` / ``VIRTUAL_HOST``.
        Used by discovery + config subscriber, which still run
        against a direct pika connection (MB5 migrates them to the bus).
    in_queue :
        Queue name / subject the plugin consumes ``TaskDto`` deliveries
        from. Becomes ``TaskRoute.named(in_queue)`` on the bus.
    out_queue :
        Queue name / subject the harness publishes ``TaskResultDto``
        results to. Becomes ``TaskResultRoute.named(out_queue)``.
    result_factory :
        Plugin-supplied callable that turns ``(task, plugin_output)``
        into a ``TaskResultDto``. The plugin owns its wire shape;
        the harness only stamps provenance afterwards.
    bus :
        Optional. If omitted, :func:`get_bus` is called lazily on
        :meth:`start_blocking`. Tests pass a pre-built bus
        (InMemoryBinder-backed, typically) to avoid the global.
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
        bus: Optional[MessageBus] = None,
    ) -> None:
        self.plugin = plugin
        self.settings = settings
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.result_factory = result_factory
        self.contract = contract
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.enable_discovery = enable_discovery and contract is not None
        self.enable_config = enable_config and contract is not None
        self._bus = bus
        # Routes derived from the legacy string params — callers pass
        # physical queue names today; MB5+ can migrate to contract-based
        # routes (TaskRoute.for_category(...)) when plugin configs update.
        self._in_route = TaskRoute.named(in_queue)
        self._out_route = TaskResultRoute.named(out_queue)
        self._stopping = threading.Event()
        self._task_handle: Optional[ConsumerHandle] = None
        self._heartbeat_loop: Optional[HeartbeatLoop] = None
        self._discovery_publisher: Optional[DiscoveryPublisher] = None
        self._config_subscriber: Optional[ConfigSubscriber] = None
        # G.1 cooperative cancel: populated in start_blocking().
        self._cancel_listener: Optional[Any] = None

    # ------------------------------------------------------------------
    # Per-message flow
    # ------------------------------------------------------------------

    def _handle_task(self, envelope: Envelope) -> None:
        """Bus-side entry point: validate → run → publish result.

        Raising propagates up to the binder, which routes through
        :func:`classify_exception` → REQUEUE / DLQ per policy. Returns
        ``None`` on success: the binder acks.

        :class:`JobCancelledError` is handled specially (G.1): the
        plugin's progress reporter raised because an operator
        cancelled the job mid-flight. We convert that into a
        CANCELLED-flavoured :class:`TaskResultDto`, publish it so
        the result processor + UI see the transition, and return
        normally so the binder acks. Re-raising would push the task
        to the DLQ, which confuses operators ("why is my cancelled
        task in the DLQ?").
        """
        # Drain any pending config between deliveries so the plugin
        # sees the new settings on the very next run. A bad configure()
        # must not poison the task — swallow + log.
        self._apply_pending_config()

        task = self._task_from_envelope(envelope)
        validated = self.plugin.input_schema().model_validate(task.data)

        try:
            plugin_output = self.plugin.run(validated)
        except JobCancelledError as exc:
            logger.info(
                "PluginBrokerRunner[%s]: task %s cancelled (%s); publishing cancelled result",
                self.plugin.get_info().name, task.id, exc,
            )
            result = self._build_cancelled_result(task, str(exc))
            self._stamp_provenance(result)
            self._publish_result(result)
            return

        result = self.result_factory(task, plugin_output)
        self._stamp_provenance(result)
        self._publish_result(result)

    def _publish_result(self, result: TaskResultDto) -> None:
        """Publish the result envelope, logging a failed send."""
        result_envelope = Envelope.wrap(
            source=f"magellon/plugins/{self.plugin.get_info().name}",
            type="magellon.task.result",
            subject=self._out_route.subject,
            data=result,
        )
        receipt = self._require_bus().tasks.send(self._out_route, result_envelope)
        if not receipt.ok:
            logger.error(
                "PluginBrokerRunner[%s]: result publish failed on %s: %s",
                self.plugin.get_info().name,
                self._out_route.subject,
                receipt.error,
            )

    def _build_cancelled_result(self, task: TaskDto, reason: str) -> TaskResultDto:
        """Minimal cancelled-status result. Uses ``FAILED`` as the wire
        status because the TaskStatus enum doesn't have a CANCELLED
        code today; the ``message`` field carries the human-readable
        distinction, and ``output_data`` includes a ``cancelled=True``
        flag so downstream consumers that care can distinguish the
        two. Upgrading to a real CANCELLED enum value is a later
        polish (touches TaskOutputProcessor status mapping).

        ``image_id`` lives inside ``task.data`` on every category's
        TaskDto — the top-level TaskDto is category-agnostic. Pulling
        it out lets the result processor project against the right
        image row; without it the cancelled status floats without
        anchor."""
        image_id = None
        if isinstance(task.data, dict):
            image_id = task.data.get("image_id")
        return TaskResultDto(
            task_id=task.id,
            image_id=image_id,
            type=task.type,
            code=FAILED.code,
            message=f"cancelled: {reason}",
            status=FAILED,
            output_data={"cancelled": True, "reason": reason},
            job_id=task.job_id,
        )

    @staticmethod
    def _task_from_envelope(envelope: Envelope) -> TaskDto:
        """Pull the ``TaskDto`` out of the envelope's ``data``.

        Binder reconstructs envelopes with ``data`` as a dict (JSON
        on the wire was a raw TaskDto shape); we validate back into
        the typed model here. If someone publishes with
        ``Envelope.wrap(data=task_dto)`` on the producer side, data
        will already be a TaskDto instance — model_validate handles
        both shapes.
        """
        data = envelope.data
        if isinstance(data, TaskDto):
            return data
        return TaskDto.model_validate(data)

    # Legacy pure-function shape used by pre-MB4.1 tests. Accepts raw
    # TaskDto JSON bytes, returns raw TaskResultDto JSON bytes — the
    # shape the old pika callback had. Useful for plugin-level tests
    # that want to exercise the transformation without the bus.
    def _process(self, body: bytes) -> bytes:
        self._apply_pending_config()
        task = TaskDto.model_validate_json(body.decode("utf-8"))
        validated = self.plugin.input_schema().model_validate(task.data)
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
    # Discovery + config (still on direct pika — MB5 migrates)
    # ------------------------------------------------------------------

    def _start_discovery(self) -> None:
        """Publish the announce manifest + start the heartbeat loop.

        Idempotent: safe to call twice. Lifecycle plumbing lives in
        :mod:`magellon_sdk.runner.lifecycle` — will absorb into
        ``bus.events.publish`` in MB5.
        """
        if not self.enable_discovery or self.contract is None:
            return
        publisher, heartbeat, _announce = start_discovery(
            settings=self.settings,
            plugin=self.plugin,
            contract=self.contract,
            heartbeat_interval_seconds=self.heartbeat_interval_seconds,
            task_queue=self.in_queue,
            existing_publisher=self._discovery_publisher,
            existing_heartbeat=self._heartbeat_loop,
        )
        self._discovery_publisher = publisher
        self._heartbeat_loop = heartbeat

    def _start_config_subscriber(self) -> None:
        if not self.enable_config or self.contract is None:
            return
        self._config_subscriber = start_config_subscriber(
            settings=self.settings,
            contract=self.contract,
            existing=self._config_subscriber,
        )

    def _apply_pending_config(self) -> None:
        """Drain the subscriber buffer and hand it to the plugin.

        Called from :meth:`_handle_task` between deliveries — never
        while ``execute()`` is running.
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

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _require_bus(self) -> MessageBus:
        """Resolve the bus, with a fallback that keeps pre-MB4.2
        plugins working.

        Lookup order:
        1. ``self._bus`` if the caller passed one explicitly.
        2. :func:`get_bus` if a bus is installed (plugin main.py that
           called ``install_rmq_bus(...)`` — MB4.2+ pattern).
        3. Fallback: build an :class:`RmqBinder` from
           ``self.settings`` and install it. Keeps plugins whose
           ``main.py`` hasn't been migrated to the bootstrap helper
           working transparently.
        """
        if self._bus is not None:
            return self._bus
        try:
            self._bus = get_bus()
            return self._bus
        except RuntimeError:
            # No factory registered — build + install one from our
            # RMQ settings. Matches what install_rmq_bus would do.
            from magellon_sdk.bus.bootstrap import install_rmq_bus

            logger.info(
                "PluginBrokerRunner: no bus installed — auto-installing RmqBus "
                "from runner settings. For MB4.2+ plugin main.py should call "
                "install_rmq_bus() explicitly at startup."
            )
            self._bus = install_rmq_bus(self.settings)
            return self._bus

    def _start_cancel_listener(self, bus: MessageBus) -> None:
        """G.1: subscribe to the per-job cancel subject so each
        delivery's progress checkpoint can see its cancel flag flip."""
        # Lazy import: cancel_registry depends on magellon_sdk.bus which
        # may not be initialized in every test context.
        from magellon_sdk.bus.services.cancel_registry import start_cancel_listener
        try:
            self._cancel_listener = start_cancel_listener(bus=bus)
        except Exception:
            logger.exception(
                "PluginBrokerRunner[%s]: cancel listener failed to start "
                "(cooperative cancel disabled for this process)",
                self.plugin.get_info().name,
            )

    def start_blocking(self) -> None:
        """Register the task consumer on the bus + run until shutdown.

        Reconnect is the binder's concern now; this method trusts the
        bus to keep the consumer alive across transient broker
        blips. Discovery / config still open their own pika
        connections and have independent reconnect behavior (MB5
        folds them into the bus).
        """
        bus = self._require_bus()
        self._task_handle = bus.tasks.consumer(
            self._in_route, self._handle_task
        )
        self._start_discovery()
        self._start_config_subscriber()
        self._start_cancel_listener(bus)
        logger.info(
            "PluginBrokerRunner[%s]: consuming %s, publishing %s",
            self.plugin.get_info().name,
            self._in_route.subject,
            self._out_route.subject,
        )
        try:
            self._task_handle.run_until_shutdown()
        finally:
            self.stop()

    def stop(self) -> None:
        self._stopping.set()
        if self._task_handle is not None:
            try:
                self._task_handle.close()
            except Exception as e:  # noqa: BLE001
                logger.debug("task handle close failed: %s", e)
            self._task_handle = None
        if self._heartbeat_loop is not None:
            self._heartbeat_loop.stop()
        if self._discovery_publisher is not None:
            self._discovery_publisher.close()
        if self._config_subscriber is not None:
            self._config_subscriber.stop()
        if self._cancel_listener is not None:
            try:
                self._cancel_listener.stop()
            except Exception as e:  # noqa: BLE001
                logger.debug("cancel listener stop failed: %s", e)
            self._cancel_listener = None


__all__ = ["PluginBrokerRunner", "ResultFactory"]
