"""Handicap configuration for Silksong boss environments."""

from dataclasses import dataclass


@dataclass
class HandicapConfig:
    """Configuration for player handicaps."""

    has_clawline: bool = True
    has_cling_grip: bool = True
    has_dash: bool = True
    has_double_jump: bool = True
    has_drifters_cloak: bool = True
    has_needle_strike: bool = True
    has_silkspear: bool = True
    hunter_crest_version: int = 3
    max_health: int = 9
    max_silk: int = 18
    needle_upgrades: int = 4
    silk_hearts: int = 3
