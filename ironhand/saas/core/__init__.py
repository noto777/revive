"""
Core business logic package for IronHand SaaS.

Pure strategy logic with no I/O dependencies.
Ported from the live bot with bug fixes and regime system removed.
"""

from .core_manager import (
    CorePositionManager,
    ExitMode,
    ExitSignal,
    PositionState,
)
from .indicators import (
    calculate_atr,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_rsi,
    calculate_sma,
    calculate_wavetrend,
    smooth_curve,
)
from .strategy_logic import CoreStrategyLogic, LadderRung

__all__ = [
    # Strategy logic
    "CoreStrategyLogic",
    "LadderRung",
    # Core position management
    "CorePositionManager",
    "ExitMode",
    "ExitSignal",
    "PositionState",
    # Indicators
    "calculate_rsi",
    "calculate_bollinger_bands",
    "calculate_atr",
    "calculate_wavetrend",
    "calculate_ema",
    "calculate_sma",
    "smooth_curve",
]
