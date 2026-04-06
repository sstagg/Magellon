"""Serialization utilities for converting SQLAlchemy model values to JSON-safe types."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID


def serialize_datetime(dt: datetime) -> str:
    return dt.isoformat() if dt else None


def serialize_uuid(value: UUID) -> str:
    return str(value) if value else None


def safe_decimal(value):
    if value is None:
        return None
    try:
        if isinstance(value, Decimal):
            return value.normalize()
        str_val = f"{value:.20f}" if isinstance(value, float) else str(value)
        return Decimal(str_val)
    except InvalidOperation:
        raise ValueError(f"Invalid decimal value: {value}")


def safe_bigint(value):
    try:
        return int(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def safe_bit(value):
    return bool(value) if value is not None else None
