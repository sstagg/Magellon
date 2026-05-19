"""Request/reply routes.

RPC routes are for short control-plane calls to one available plugin
replica. They deliberately live outside task routes so request/reply
does not become a second job system.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from magellon_sdk.categories.contract import CategoryContract


@dataclass(frozen=True)
class RpcRoute:
    """Where an RPC request is sent.

    ``subject`` is the broker-neutral route and ``physical_queue`` lets
    CoreService pin to a discovered plugin queue without exposing plugin
    container IPs or ports.
    """

    subject: str
    physical_queue: Optional[str] = None

    @classmethod
    def for_category(cls, contract: CategoryContract) -> "RpcRoute":
        return cls(subject=f"magellon.rpc.{contract.category.name.lower()}")

    @classmethod
    def for_backend(
        cls,
        contract: CategoryContract,
        backend_id: str,
        queue: Optional[str] = None,
    ) -> "RpcRoute":
        return cls(
            subject=f"magellon.rpc.{contract.category.name.lower()}.{backend_id.lower()}",
            physical_queue=queue,
        )

    @classmethod
    def named(cls, subject: str, queue: Optional[str] = None) -> "RpcRoute":
        return cls(subject=subject, physical_queue=queue)


__all__ = ["RpcRoute"]
