from __future__ import annotations

import logging

DOMAIN = "neakasa"
AES_KEY_DEFAULT = b"3J74PRUE5TKPJP32"
AES_IV_DEFAULT = b"QB8GC2X6WK39FF93"

SUPPORTED_CATEGORY_KEYS: frozenset[str] = frozenset({"CatLitter", "petFeeder"})

# Riko wet-meal feeder portion bounds and water ratio (product UI ranges).
FEED_FOOD_MIN_G = 3
FEED_FOOD_MAX_G = 15
FEED_WATER_RATIO_MIN = 1
FEED_WATER_RATIO_MAX = 5

# On the wire a meal's water is an amount of water in grams (`defFdCfg.water` and
# the ``feedOnce`` ``water`` argument), never the ratio index: the ratio is applied
# to the portion. Observed operation of the machine confirms this: sending the ratio
# index made the machine keep adding water until it reported clogged water sprays.

# Used only when the machine reports `{food:0,water:0}`: that is its "never configured"
# state, not a ratio of 0/0. Ratio 1 is the smallest amount on offer, so an unconfigured
# machine waters less than it grinds rather than the integration guessing high.
DEFAULT_FEED_FOOD_G = 5
DEFAULT_FEED_WATER_RATIO = 1

LOGGER = _LOGGER = logging.getLogger(__package__)
