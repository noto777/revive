"""
Strategy executor - per-tenant strategy loop.

Replaces the monolithic main.py with a clean, async executor that:
- Runs one per strategy instance
- Fetches market data and calculates indicators
- Manages ladder placement and fills
- Handles core position exits
- Publishes events to the event bus
- Respects shutdown signals
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
import structlog

from sqlalchemy.ext.asyncio import AsyncSession

from core.strategy_logic import CoreStrategyLogic
from core.core_manager import CorePositionManager
from core.indicators import IndicatorEngine
from brokers.base import BrokerInterface, OrderRequest, OrderSide, OrderType
from engine.events import (
    get_event_bus,
    EventType,
    OrderEvent,
    PositionEvent,
    LadderEvent,
    StatusEvent,
    ErrorEvent,
    CoreManagementEvent,
)
from engine.signals import ShutdownManager
from db.models import Strategy, Position, Order, Execution
from settings import StrategyConfig
from sqlalchemy import select, update

logger = structlog.get_logger()


class StrategyExecutor:
    """
    Executes a single strategy in an async loop.
    
    Lifecycle:
    1. Load strategy config from DB
    2. Connect to broker
    3. Run main loop (check interval)
    4. On each cycle:
       - Fetch market data
       - Calculate indicators (RSI, BBands, ATR, WaveTrend)
       - Generate ladder
       - Check for fills
       - Manage exits (rebalancing, scale-out, profit lock)
       - Save state snapshot
    5. On shutdown signal, gracefully disconnect
    """
    
    def __init__(
        self,
        strategy_id: str,
        tenant_id: str,
        broker: BrokerInterface,
        db_session: AsyncSession,
        shutdown_manager: ShutdownManager,
    ):
        self.strategy_id = strategy_id
        self.tenant_id = tenant_id
        self.broker = broker
        self.db_session = db_session
        self.shutdown_manager = shutdown_manager
        self.event_bus = get_event_bus()
        
        self.config: Optional[StrategyConfig] = None
        self.symbol: Optional[str] = None
        self.strategy_logic: Optional[CoreStrategyLogic] = None
        self.core_manager: Optional[CorePositionManager] = None
        self.indicator_engine = IndicatorEngine()
        
        self.logger = logger.bind(
            tenant_id=tenant_id,
            strategy_id=strategy_id,
        )
        
    async def initialize(self) -> bool:
        """Load strategy config and initialize components."""
        try:
            # Load strategy from DB
            result = await self.db_session.execute(
                select(Strategy).where(Strategy.id == self.strategy_id)
            )
            strategy = result.scalar_one_or_none()
            
            if not strategy:
                self.logger.error("strategy_not_found")
                return False
            
            # Parse config
            self.symbol = strategy.symbol
            self.config = StrategyConfig(**strategy.config)
            
            # Initialize components
            self.strategy_logic = CoreStrategyLogic(self.config)
            self.core_manager = CorePositionManager(self.config)
            
            # Connect to broker
            await self.broker.connect()
            
            self.logger.info(
                "executor_initialized",
                symbol=self.symbol,
                config=self.config.dict(),
            )
            
            return True
            
        except Exception as e:
            self.logger.error("initialization_failed", error=str(e), exc_info=True)
            await self._publish_error("initialization_failed", str(e))
            return False
    
    async def run(self) -> None:
        """Main execution loop."""
        try:
            # Mark strategy as running
            await self._update_status("running")
            await self._publish_status("stopped", "running", "Strategy started")
            
            self.logger.info("executor_started")
            
            while not self.shutdown_manager.should_shutdown():
                try:
                    await self._execute_cycle()
                except Exception as e:
                    self.logger.error(
                        "cycle_error",
                        error=str(e),
                        exc_info=True,
                    )
                    await self._publish_error("cycle_error", str(e))
                
                # Sleep until next check or shutdown signal
                try:
                    await asyncio.wait_for(
                        self.shutdown_manager.wait_for_shutdown(),
                        timeout=self.config.check_interval,
                    )
                    break  # Shutdown signal received
                except asyncio.TimeoutError:
                    continue  # Timeout reached, run next cycle
            
            self.logger.info("executor_stopping")
            
        finally:
            await self.cleanup()
    
    async def _execute_cycle(self) -> None:
        """Execute one iteration of the strategy loop."""
        cycle_start = datetime.utcnow()
        
        # 1. Fetch market data
        df = await self.broker.get_market_data(
            symbol=self.symbol,
            duration="7 D",
            bar_size="1 hour",
        )
        
        if df.empty or len(df) < 50:
            self.logger.warning("insufficient_market_data", rows=len(df))
            return
        
        # 2. Calculate indicators
        current_price = await self.broker.get_current_price(self.symbol)
        indicators = self.indicator_engine.calculate_all(df, current_price)
        
        self.logger.debug(
            "indicators_calculated",
            rsi=float(indicators['rsi']),
            atr=float(indicators['atr']),
            price=float(current_price),
        )
        
        # 3. Get account and position state
        account_summary = await self.broker.get_account_summary()
        positions = await self.broker.get_positions()
        
        # Filter for this strategy's symbol
        current_positions = [p for p in positions if p.symbol == self.symbol]
        
        # 4. Generate ladder
        ladder = self.strategy_logic.generate_ladder(
            current_price=current_price,
            atr_value=indicators['atr'],
            account_value=account_summary.net_liquidation,
            existing_positions=current_positions,
        )
        
        if ladder:
            await self._publish_ladder(ladder, current_price)
            await self._place_ladder_orders(ladder)
        
        # 5. Check for fills and update positions
        await self._process_fills()
        
        # 6. Manage exits (rebalancing, scale-out, profit lock)
        if current_positions:
            await self._manage_exits(
                positions=current_positions,
                current_price=current_price,
                account_value=account_summary.net_liquidation,
            )
        
        # 7. Save snapshot
        await self._save_snapshot({
            'timestamp': datetime.utcnow().isoformat(),
            'price': float(current_price),
            'indicators': {k: float(v) for k, v in indicators.items()},
            'positions': [
                {
                    'entry_price': float(p.avg_price),
                    'quantity': float(p.quantity),
                    'pnl': float(p.unrealized_pnl or 0),
                }
                for p in current_positions
            ],
            'ladder': ladder,
            'account_value': float(account_summary.net_liquidation),
        })
        
        cycle_duration = (datetime.utcnow() - cycle_start).total_seconds()
        self.logger.debug("cycle_completed", duration=cycle_duration)
    
    async def _place_ladder_orders(self, ladder: list) -> None:
        """Place limit buy orders for ladder rungs."""
        for i, rung in enumerate(ladder):
            try:
                order_id = await self.broker.place_order(OrderRequest(
                    symbol=self.symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.LIMIT,
                    quantity=Decimal(str(rung['quantity'])),
                    limit_price=Decimal(str(rung['price'])),
                ))
                
                # Save to DB
                order = Order(
                    strategy_id=self.strategy_id,
                    tenant_id=self.tenant_id,
                    broker_order_id=order_id,
                    symbol=self.symbol,
                    side="BUY",
                    order_type="LMT",
                    quantity=Decimal(str(rung['quantity'])),
                    limit_price=Decimal(str(rung['price'])),
                    status="pending",
                )
                self.db_session.add(order)
                await self.db_session.commit()
                
                # Publish event
                await self.event_bus.publish(OrderEvent(
                    event_type=EventType.ORDER_PLACED,
                    tenant_id=self.tenant_id,
                    strategy_id=self.strategy_id,
                    symbol=self.symbol,
                    broker_order_id=order_id,
                    side="BUY",
                    order_type="LMT",
                    quantity=Decimal(str(rung['quantity'])),
                    limit_price=Decimal(str(rung['price'])),
                ))
                
            except Exception as e:
                self.logger.error(
                    "order_placement_failed",
                    rung_index=i,
                    error=str(e),
                )
                await self._publish_error("order_placement_failed", str(e))
    
    async def _process_fills(self) -> None:
        """Check for filled orders and update positions."""
        # This would be called by broker's fill callback in production
        # For now, we'll poll for fills periodically
        pass
    
    async def _manage_exits(
        self,
        positions: list,
        current_price: Decimal,
        account_value: Decimal,
    ) -> None:
        """Execute exit strategies (rebalancing, scale-out, profit lock)."""
        total_position_value = sum(
            p.quantity * current_price for p in positions
        )
        core_pct = (total_position_value / account_value) * Decimal('100')
        
        # Get exit action from core manager
        action = self.core_manager.get_exit_action(
            core_allocation_pct=core_pct,
            current_price=current_price,
            positions=positions,
        )
        
        if action:
            await self._execute_exit_action(action, positions, current_price)
    
    async def _execute_exit_action(
        self,
        action: dict,
        positions: list,
        current_price: Decimal,
    ) -> None:
        """Execute an exit action (sell order)."""
        try:
            quantity = Decimal(str(action['quantity']))
            order_id = await self.broker.place_order(OrderRequest(
                symbol=self.symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=quantity,
            ))
            
            # Save to DB
            order = Order(
                strategy_id=self.strategy_id,
                tenant_id=self.tenant_id,
                broker_order_id=order_id,
                symbol=self.symbol,
                side="SELL",
                order_type="MKT",
                quantity=quantity,
                status="pending",
            )
            self.db_session.add(order)
            await self.db_session.commit()
            
            # Publish event
            event_type_map = {
                'rebalance': EventType.CORE_REBALANCE,
                'scale_out': EventType.CORE_SCALE_OUT,
                'profit_lock': EventType.PROFIT_LOCK_TRIGGERED,
            }
            
            await self.event_bus.publish(CoreManagementEvent(
                event_type=event_type_map.get(action['type'], EventType.CORE_SCALE_OUT),
                tenant_id=self.tenant_id,
                strategy_id=self.strategy_id,
                symbol=self.symbol,
                action=action['type'],
                core_pct=float(action.get('core_pct', 0)),
                profit_pct=float(action.get('profit_pct', 0)),
                quantity=quantity,
                price=current_price,
            ))
            
        except Exception as e:
            self.logger.error("exit_action_failed", action=action, error=str(e))
            await self._publish_error("exit_action_failed", str(e))
    
    async def _publish_ladder(self, ladder: list, current_price: Decimal) -> None:
        """Publish ladder event."""
        total_value = sum(r['quantity'] * r['price'] for r in ladder)
        
        await self.event_bus.publish(LadderEvent(
            event_type=EventType.LADDER_PLACED,
            tenant_id=self.tenant_id,
            strategy_id=self.strategy_id,
            symbol=self.symbol,
            num_rungs=len(ladder),
            start_price=Decimal(str(ladder[0]['price'])) if ladder else current_price,
            end_price=Decimal(str(ladder[-1]['price'])) if ladder else current_price,
            total_value=Decimal(str(total_value)),
        ))
    
    async def _publish_status(
        self,
        old_status: str,
        new_status: str,
        message: str,
    ) -> None:
        """Publish status change event."""
        await self.event_bus.publish(StatusEvent(
            event_type=EventType.STRATEGY_STARTED if new_status == "running" else EventType.STRATEGY_STOPPED,
            tenant_id=self.tenant_id,
            strategy_id=self.strategy_id,
            symbol=self.symbol or "",
            old_status=old_status,
            new_status=new_status,
            message=message,
        ))
    
    async def _publish_error(self, error_type: str, message: str) -> None:
        """Publish error event."""
        await self.event_bus.publish(ErrorEvent(
            event_type=EventType.STRATEGY_ERROR,
            tenant_id=self.tenant_id,
            strategy_id=self.strategy_id,
            symbol=self.symbol or "",
            error_type=error_type,
            error_message=message,
        ))
    
    async def _update_status(self, status: str) -> None:
        """Update strategy status in DB."""
        await self.db_session.execute(
            update(Strategy)
            .where(Strategy.id == self.strategy_id)
            .values(status=status, updated_at=datetime.utcnow())
        )
        await self.db_session.commit()
    
    async def _save_snapshot(self, snapshot: dict) -> None:
        """Save dashboard snapshot to DB."""
        from db.models import StrategySnapshot
        
        snap = StrategySnapshot(
            strategy_id=self.strategy_id,
            tenant_id=self.tenant_id,
            snapshot=snapshot,
        )
        self.db_session.add(snap)
        await self.db_session.commit()
    
    async def cleanup(self) -> None:
        """Cleanup on shutdown."""
        try:
            await self._update_status("stopped")
            await self._publish_status("running", "stopped", "Strategy stopped")
            await self.broker.disconnect()
            self.logger.info("executor_cleaned_up")
        except Exception as e:
            self.logger.error("cleanup_error", error=str(e))
