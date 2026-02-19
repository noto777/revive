"""
Core Strategy Logic - Ladder Generation

Pure business logic for ATR-based buy ladder generation.
Ported from live bot's strategy_logic.py with bug fixes applied.

No I/O, no broker dependencies - just calculations.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

import numpy as np

from exceptions import InvalidIndicatorData, LadderGenerationError
from logger import get_logger

logger = get_logger()


@dataclass
class LadderRung:
    """
    A single rung on the buy ladder.
    
    Attributes:
        rung_index: Position in ladder (0 = closest to current price)
        price: Limit order price
        quantity: Number of shares to buy
        notional_usd: Total USD value of this rung
        atr_distance: ATR multiplier from current price
    """
    rung_index: int
    price: Decimal
    quantity: Decimal
    notional_usd: Decimal
    atr_distance: Decimal
    
    def __repr__(self):
        return (
            f"Rung {self.rung_index}: "
            f"{self.quantity} @ ${self.price:.2f} "
            f"(${self.notional_usd:.2f}, {self.atr_distance:.2f} ATR)"
        )


class CoreStrategyLogic:
    """
    Generates ATR-based buy ladders with curved distribution.
    
    This is the core "dip buying" logic:
    - Tries to fit max_slots rungs below current price
    - Uses ATR multipliers with power curve for non-linear distribution
    - Increases position size per rung (geometric progression)
    - Ensures minimum trade size per rung
    
    Removed regime system - all params now configurable per strategy.
    """
    
    def __init__(
        self,
        min_ladder_trade_usd: Decimal = Decimal("500.00"),
        start_atr: Decimal = Decimal("0.2"),
        end_atr: Decimal = Decimal("0.6"),
        distribution_curve: Decimal = Decimal("1.0"),
        size_increase_factor: Decimal = Decimal("1.25"),
    ):
        """
        Initialize strategy logic with configuration.
        
        Args:
            min_ladder_trade_usd: Minimum trade size in USD per rung
            start_atr: Starting ATR multiplier (closest rung)
            end_atr: Ending ATR multiplier (deepest rung)
            distribution_curve: Exponent for spacing curve (1.0=linear, >1=bunched near start)
            size_increase_factor: Multiplier per rung (e.g., 1.25 = 25% larger each rung)
        """
        self.min_ladder_trade_usd = min_ladder_trade_usd
        self.start_atr = start_atr
        self.end_atr = end_atr
        self.distribution_curve = distribution_curve
        self.size_increase_factor = size_increase_factor
        
        logger.debug(
            "strategy_logic_initialized",
            min_trade=float(min_ladder_trade_usd),
            start_atr=float(start_atr),
            end_atr=float(end_atr),
            curve=float(distribution_curve),
            size_factor=float(size_increase_factor),
        )
    
    def generate_ladder(
        self,
        current_price: Decimal,
        atr_value: Decimal,
        buying_power: Decimal,
        max_slots: int = 10,
    ) -> List[LadderRung]:
        """
        Generate buy ladder with look-ahead sizing optimization.
        
        Strategy:
        1. Try fitting max_slots rungs with increasing position sizes
        2. If smallest rung is below min_trade_usd, reduce slot count
        3. Repeat until all rungs meet minimum size or down to 1 slot
        
        Args:
            current_price: Current market price
            atr_value: Current ATR indicator value
            buying_power: Available capital in USD
            max_slots: Maximum number of ladder rungs to generate
            
        Returns:
            List of ladder rungs (empty if cannot fit any valid rungs)
            
        Raises:
            InvalidIndicatorData: If price or ATR are invalid
            LadderGenerationError: If ladder generation fails
        """
        # Validation
        if current_price <= 0:
            raise InvalidIndicatorData(f"Invalid current_price: {current_price}")
        if atr_value <= 0:
            raise InvalidIndicatorData(f"Invalid atr_value: {atr_value}")
        if buying_power <= 0:
            logger.warning("zero_buying_power", buying_power=float(buying_power))
            return []
        
        logger.debug(
            "generating_ladder",
            price=float(current_price),
            atr=float(atr_value),
            buying_power=float(buying_power),
            max_slots=max_slots,
        )
        
        # Look-ahead sizing: Try max_slots down to 1
        for num_slots in range(max_slots, 0, -1):
            try:
                ladder = self._try_generate_ladder(
                    current_price=current_price,
                    atr_value=atr_value,
                    buying_power=buying_power,
                    num_slots=num_slots,
                )
                
                # Check if smallest rung meets minimum
                min_notional = min(rung.notional_usd for rung in ladder)
                if min_notional >= self.min_ladder_trade_usd:
                    logger.info(
                        "ladder_generated",
                        num_rungs=len(ladder),
                        total_notional=float(sum(r.notional_usd for r in ladder)),
                        min_rung=float(min_notional),
                    )
                    return ladder
                
            except Exception as e:
                logger.warning("ladder_generation_attempt_failed", num_slots=num_slots, error=str(e))
                continue
        
        # Could not generate any valid ladder
        logger.warning("no_valid_ladder_generated", max_slots=max_slots)
        return []
    
    def _try_generate_ladder(
        self,
        current_price: Decimal,
        atr_value: Decimal,
        buying_power: Decimal,
        num_slots: int,
    ) -> List[LadderRung]:
        """
        Attempt to generate a ladder with specific number of slots.
        
        Args:
            current_price: Current market price
            atr_value: ATR value
            buying_power: Available capital
            num_slots: Number of rungs to generate
            
        Returns:
            List of ladder rungs
            
        Raises:
            LadderGenerationError: If generation fails
        """
        if num_slots <= 0:
            raise LadderGenerationError("num_slots must be positive")
        
        # Generate curved ATR multipliers
        atr_multipliers = self._generate_atr_multipliers(num_slots)
        
        # Calculate size increase factors (geometric progression)
        size_factors = [
            float(self.size_increase_factor) ** i
            for i in range(num_slots)
        ]
        total_size_factor = sum(size_factors)
        
        # Distribute buying power across rungs
        ladder = []
        for i in range(num_slots):
            atr_mult = Decimal(str(atr_multipliers[i]))
            
            # Price is current - (ATR * multiplier)
            price = current_price - (atr_value * atr_mult)
            if price <= 0:
                raise LadderGenerationError(f"Rung {i} price <= 0")
            
            # Notional allocation for this rung
            notional = buying_power * Decimal(str(size_factors[i])) / Decimal(str(total_size_factor))
            
            # Quantity = notional / price
            quantity = notional / price
            
            rung = LadderRung(
                rung_index=i,
                price=price,
                quantity=quantity,
                notional_usd=notional,
                atr_distance=atr_mult,
            )
            ladder.append(rung)
        
        return ladder
    
    def _generate_atr_multipliers(self, num_slots: int) -> np.ndarray:
        """
        Generate curved ATR multipliers using power function.
        
        Args:
            num_slots: Number of multipliers to generate
            
        Returns:
            Array of ATR multipliers (ascending)
            
        Note:
            - distribution_curve = 1.0 produces linear spacing
            - distribution_curve > 1.0 bunches rungs closer to start
            - distribution_curve < 1.0 spreads them more evenly
        """
        if num_slots == 1:
            # Single slot: use midpoint between start and end
            return np.array([(float(self.start_atr) + float(self.end_atr)) / 2.0])
        
        # Linear spacing in [0, 1]
        linear = np.linspace(0, 1, num_slots)
        
        # Apply power curve
        curve_exp = float(self.distribution_curve)
        curved = linear ** curve_exp
        
        # Scale to [start_atr, end_atr]
        start = float(self.start_atr)
        end = float(self.end_atr)
        multipliers = start + (curved * (end - start))
        
        return multipliers
