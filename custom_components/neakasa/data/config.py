"""Shapes of the data persisted on the config entry."""

from __future__ import annotations

from typing import TypedDict


class NeakasaConfigData(TypedDict):
    """Shape of the credentials + device selection persisted on the config entry."""

    device_id: str
    friendly_name: str
    username: str
    password: str