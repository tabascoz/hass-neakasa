from __future__ import annotations

import logging

DOMAIN = "neakasa"
AES_KEY_DEFAULT = b"3J74PRUE5TKPJP32"
AES_IV_DEFAULT = b"QB8GC2X6WK39FF93"

SUPPORTED_CATEGORY_KEYS: frozenset[str] = frozenset({"CatLitter", "petFeeder"})

# Riko wet-meal feeder portion/water-ratio bounds (product UI ranges, in grams).
FEED_FOOD_MIN_G = 3
FEED_FOOD_MAX_G = 15
FEED_WATER_RATIO_MIN = 1
FEED_WATER_RATIO_MAX = 5

LOGGER = _LOGGER = logging.getLogger(__package__)
