"""Runtime data stored on the config entry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from ..coordinator import NeakasaCoordinator


type NeakasaConfigEntry = ConfigEntry[NeakasaData]


@dataclass
class NeakasaData:
    """Data stored on entry.runtime_data for the Neakasa integration."""

    coordinator: NeakasaCoordinator