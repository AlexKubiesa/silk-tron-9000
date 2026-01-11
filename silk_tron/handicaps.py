"""Handicap configuration for Silksong boss environments."""

from dataclasses import dataclass


@dataclass
class HandicapConfig:
    """Configuration for player handicaps."""

    has_clawline: bool = True
    has_dash: bool = True
