"""
Core Position Manager - Exit Strategies

Manages position exits with two modes:
1. Rebalancing mode (when core position exceeds max allocation)
2. Standard scale-out mode (profit-based incremental selling)

Plus universal profit lock (trailing stop).

Ported from live bot's core_manager.py - pure business logic.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Tuple

from logger import get_logger

logger = get_logger()


class ExitMode(Enum):
    """Core position exit strategy mode."""
    REBALANCING = "rebalancing"  # Trim oversized position
    SCALE_OUT = "scale_out"      # Profit-based incremental exits
    PROFIT_LOCK = "profit_lock"  # Trailing stop triggered


@dataclass
class ExitSignal:
    """
    Signal to exit a portion of the position.
    
    Attributes:
        mode: Which exit strategy triggered
        quantity_pct: Percentage of position to sell (0-100)
        reason: Human-readable reason for the exit
        trigger_price: Price that triggered the exit (for logging)
    """
    mode: ExitMode
    quantity_pct: Decimal
    reason: str
    trigger_price: Decimal
    
    def __repr__(self):
        return f"ExitSignal({self.mode.value}, {self.quantity_pct}%, {self.reason})"


@dataclass
class PositionState:
    """
    Current position state for exit strategy calculations.
    
    Attributes:
        quantity: Current position size (shares)
        avg_entry_price: Average entry price
        current_price: Current market price
        account_value: Total account value (for allocation %)
    """
    quantity: Decimal
    avg_entry_price: Decimal
    current_price: Decimal
    account_value: Decimal
    
    @property
    def notional_value(self) -> Decimal:
        """Current notional value of position."""
        return self.quantity * self.current_price
    
    @property
    def allocation_pct(self) -> Decimal:
        """Position as % of account value."""
        if self.account_value <= 0:
            return Decimal("0")
        return (self.notional_value / self.account_value) * Decimal("100")
    
    @property
    def profit_pct(self) -> Decimal:
        """Unrealized profit as % of entry price."""
        if self.avg_entry_price <= 0:
            return Decimal("0")
        return ((self.current_price - self.avg_entry_price) / self.avg_entry_price) * Decimal("100")


class CorePositionManager:
    """
    Manages core position exits using dual-mode strategy.
    
    Mode Selection:
    - If position allocation > (max_core_pct + hysteresis_gap): REBALANCING mode
    - Else: SCALE_OUT mode
    
    REBALANCING mode:
    - Triggered when position is oversized (e.g., >17% of account)
    - Sells 5% of position at each 2% profit step
    - Goal: trim allocation while capturing profits
    
    SCALE_OUT mode:
    - Triggered at regular profit milestones (e.g., 8%, 12%, 16%...)
    - Sells scale_out_pct (e.g., 15%) at each step
    - scale_out_step defines spacing (e.g., 4% = sell at 4%, 8%, 12%...)
    
    PROFIT_LOCK (universal):
    - Arms when profit reaches profit_lock_arm (e.g., 12%)
    - Trails by profit_lock_trail (e.g., 4%) below high water mark
    - Sells entire position when triggered
    """
    
    def __init__(
        self,
        max_core_pct: Decimal = Decimal("15.0"),
        core_hysteresis_gap: Decimal = Decimal("2.0"),
        scale_out_pct: Decimal = Decimal("15.0"),
        scale_out_step: Decimal = Decimal("4.0"),
        profit_lock_arm: Decimal = Decimal("12.0"),
        profit_lock_trail: Decimal = Decimal("4.0"),
    ):
        """
        Initialize core position manager with configuration.
        
        Args:
            max_core_pct: Maximum core position % (e.g., 15% of account)
            core_hysteresis_gap: Gap above max to trigger rebalancing (e.g., 2%)
            scale_out_pct: Percentage to sell at each scale-out step (e.g., 15%)
            scale_out_step: Profit step size for scale-out (e.g., 4%)
            profit_lock_arm: Profit % to arm trailing stop (e.g., 12%)
            profit_lock_trail: Trail distance below high water mark (e.g., 4%)
        """
        self.max_core_pct = max_core_pct
        self.core_hysteresis_gap = core_hysteresis_gap
        self.scale_out_pct = scale_out_pct
        self.scale_out_step = scale_out_step
        self.profit_lock_arm = profit_lock_arm
        self.profit_lock_trail = profit_lock_trail
        
        # State tracking (reset per position)
        self.highest_profit_pct: Decimal = Decimal("0")
        self.profit_lock_armed: bool = False
        self.last_scale_out_profit: Decimal = Decimal("0")
        
        logger.debug(
            "core_manager_initialized",
            max_core_pct=float(max_core_pct),
            hysteresis_gap=float(core_hysteresis_gap),
            scale_out_pct=float(scale_out_pct),
            scale_out_step=float(scale_out_step),
            profit_lock_arm=float(profit_lock_arm),
            profit_lock_trail=float(profit_lock_trail),
        )
    
    def check_exit_signals(
        self,
        position: PositionState
    ) -> List[ExitSignal]:
        """
        Check for exit signals based on current position state.
        
        Args:
            position: Current position state
            
        Returns:
            List of exit signals (empty if no exits needed)
            
        Note:
            Returns at most one signal per call to avoid over-selling.
            Caller should execute the signal and re-check.
        """
        signals = []
        
        # Update high water mark
        if position.profit_pct > self.highest_profit_pct:
            self.highest_profit_pct = position.profit_pct
        
        # Check profit lock (highest priority)
        profit_lock_signal = self._check_profit_lock(position)
        if profit_lock_signal:
            return [profit_lock_signal]  # Exit entire position
        
        # Determine mode based on allocation
        rebalancing_threshold = self.max_core_pct + self.core_hysteresis_gap
        
        if position.allocation_pct > rebalancing_threshold:
            # REBALANCING mode
            signal = self._check_rebalancing_exit(position)
            if signal:
                signals.append(signal)
        else:
            # SCALE_OUT mode
            signal = self._check_scale_out_exit(position)
            if signal:
                signals.append(signal)
        
        return signals
    
    def _check_profit_lock(self, position: PositionState) -> Optional[ExitSignal]:
        """
        Check if profit lock (trailing stop) is triggered.
        
        Returns:
            ExitSignal to sell 100% if triggered, None otherwise
        """
        # Arm the profit lock when profit reaches threshold
        if position.profit_pct >= self.profit_lock_arm:
            if not self.profit_lock_armed:
                self.profit_lock_armed = True
                logger.info(
                    "profit_lock_armed",
                    profit_pct=float(position.profit_pct),
                    arm_threshold=float(self.profit_lock_arm),
                )
        
        # Check if trailing stop is hit
        if self.profit_lock_armed:
            trail_trigger = self.highest_profit_pct - self.profit_lock_trail
            
            if position.profit_pct <= trail_trigger:
                logger.info(
                    "profit_lock_triggered",
                    current_profit=float(position.profit_pct),
                    high_water_mark=float(self.highest_profit_pct),
                    trail_trigger=float(trail_trigger),
                )
                return ExitSignal(
                    mode=ExitMode.PROFIT_LOCK,
                    quantity_pct=Decimal("100"),
                    reason=f"Profit lock: trailed from {self.highest_profit_pct:.1f}% to {position.profit_pct:.1f}%",
                    trigger_price=position.current_price,
                )
        
        return None
    
    def _check_rebalancing_exit(self, position: PositionState) -> Optional[ExitSignal]:
        """
        Check for rebalancing exit (oversized position).
        
        Rebalancing logic:
        - Sells 5% of position at each 2% profit step
        - Example: Sell at 2%, 4%, 6%, 8%, etc.
        
        Returns:
            ExitSignal if rebalancing needed, None otherwise
        """
        rebalance_step = Decimal("2.0")  # Profit step for rebalancing
        rebalance_qty_pct = Decimal("5.0")  # Amount to sell each step
        
        # Calculate which step we're at
        if position.profit_pct <= 0:
            return None
        
        current_step = int(position.profit_pct / rebalance_step)
        last_step = int(self.last_scale_out_profit / rebalance_step)
        
        if current_step > last_step:
            self.last_scale_out_profit = position.profit_pct
            
            logger.info(
                "rebalancing_exit_triggered",
                allocation_pct=float(position.allocation_pct),
                profit_pct=float(position.profit_pct),
                step=current_step,
            )
            
            return ExitSignal(
                mode=ExitMode.REBALANCING,
                quantity_pct=rebalance_qty_pct,
                reason=f"Rebalancing: {position.allocation_pct:.1f}% allocation at {position.profit_pct:.1f}% profit (step {current_step})",
                trigger_price=position.current_price,
            )
        
        return None
    
    def _check_scale_out_exit(self, position: PositionState) -> Optional[ExitSignal]:
        """
        Check for standard scale-out exit.
        
        Scale-out logic:
        - Sells scale_out_pct at each scale_out_step
        - Example: With scale_out_pct=15%, scale_out_step=4%
          - Sell 15% at 4%, 8%, 12%, 16%, etc.
        
        Returns:
            ExitSignal if scale-out needed, None otherwise
        """
        if position.profit_pct <= 0:
            return None
        
        # Calculate which step we're at
        current_step = int(position.profit_pct / self.scale_out_step)
        last_step = int(self.last_scale_out_profit / self.scale_out_step)
        
        if current_step > last_step and current_step > 0:
            self.last_scale_out_profit = position.profit_pct
            
            logger.info(
                "scale_out_exit_triggered",
                profit_pct=float(position.profit_pct),
                step=current_step,
                sell_pct=float(self.scale_out_pct),
            )
            
            return ExitSignal(
                mode=ExitMode.SCALE_OUT,
                quantity_pct=self.scale_out_pct,
                reason=f"Scale-out: {position.profit_pct:.1f}% profit (step {current_step})",
                trigger_price=position.current_price,
            )
        
        return None
    
    def reset(self):
        """Reset state tracking (call when position is fully closed)."""
        self.highest_profit_pct = Decimal("0")
        self.profit_lock_armed = False
        self.last_scale_out_profit = Decimal("0")
        logger.debug("core_manager_state_reset")
