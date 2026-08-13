"""
Multi-Tenancy.

Each Telegram chat is modelled as a tenant of the casino platform. The tenant
context is resolved from the originating chat identifier before any command or
query is processed and is exposed through a thread-local context object so
that services deeper in the call stack can resolve the active tenant without
threading it through every signature.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Optional


class TenantId:
    """Value object identifying a tenant of the platform."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        if not value:
            raise ValueError("TenantId must not be empty.")
        self._value = value

    def value(self) -> str:
        return self._value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TenantId):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __repr__(self) -> str:
        return f"TenantId({self._value!r})"


class TenantContext:
    """Thread-local holder for the currently active tenant."""

    _local = threading.local()

    @classmethod
    def set_current(cls, tenant_id: Optional[TenantId]) -> None:
        cls._local.tenant_id = tenant_id

    @classmethod
    def get_current(cls) -> Optional[TenantId]:
        return getattr(cls._local, "tenant_id", None)

    @classmethod
    def require_current(cls) -> TenantId:
        tenant_id = cls.get_current()
        if tenant_id is None:
            raise RuntimeError("No tenant is bound to the current thread.")
        return tenant_id


class ITenantResolver(ABC):
    """Port for resolving the tenant identifier from a chat identifier."""

    @abstractmethod
    def resolve(self, chat_identifier: str) -> TenantId:
        raise NotImplementedError


class ChatIdentifierTenantResolver(ITenantResolver):
    """Resolves tenants directly from the stringified chat identifier."""

    def resolve(self, chat_identifier: str) -> TenantId:
        return TenantId(str(chat_identifier))