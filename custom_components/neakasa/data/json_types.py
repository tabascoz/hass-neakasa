"""Named type aliases for JSON shapes shared across the integration."""

from __future__ import annotations

from collections.abc import Mapping

type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | list[JsonValue] | Mapping[str, JsonValue]
type JsonObject = Mapping[str, JsonValue]
