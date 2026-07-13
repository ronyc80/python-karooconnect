"""Shared type aliases for Karoo API payloads."""

from __future__ import annotations

from typing import Any, TypeAlias

JsonValue: TypeAlias = dict[str, Any] | list[Any] | str | int | float | bool | None
JsonObject: TypeAlias = dict[str, JsonValue]
Activity: TypeAlias = JsonObject
ActivityDetails: TypeAlias = JsonObject
