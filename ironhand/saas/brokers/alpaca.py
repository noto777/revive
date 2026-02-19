"""
Alpaca Broker Implementation

Wraps the Alpaca Trade API for the SaaS platform.
This is the primary broker for the SaaS (NOT IBKR).
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Callable, Optional

import pandas as pd
import structlog
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide as AlpacaSide
from alpaca.trading.enums import OrderStatus as AlpacaStatus
from alpaca.trading.enums import OrderType as AlpacaType
from alpaca.trading.enums import TimeInForce
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, StopLimitOrderRequest
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from .base import (
    AccountSummary,
    BrokerInterface,
    Execution,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSide,
)

logger = structlog.get_logger()


class AlpacaBroker(BrokerInterface):
    """
    Alpaca broker implementation using alpaca-trade-api.
    
    Args:
        api_key: Alpaca API key
        secret_key: Alpaca secret key
        base_url: API base URL (paper or live)
    """
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        base_url: str = "https://paper-api.alpaca.markets"
    ):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        
        self._trading_client: Optional[TradingClient] = None
        self._data_client: Optional[StockHistoricalDataClient] = None
        self._connected = False
        self._fill_callbacks: list[Callable[[Execution], None]] = []
        
        self.logger = logger.bind(broker="alpaca", base_url=base_url)
    
    async def connect(self) -> None:
        """Establish connection to Alpaca."""
        if self._connected:
            self.logger.warning("Already connected to Alpaca")
            return
        
        try:
            # Trading client for orders and account
            self._trading_client = TradingClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
                paper=(self.base_url == "https://paper-api.alpaca.markets")
            )
            
            # Data client for market data
            self._data_client = StockHistoricalDataClient(
                api_key=self.api_key,
                secret_key=self.secret_key
            )
            
            # Test connection by fetching account
            account = self._trading_client.get_account()
            self._connected = True
            
            self.logger.info(
                "Connected to Alpaca",
                account_id=account.id,
                status=account.status
            )
            
        except Exception as e:
            self.logger.error("Failed to connect to Alpaca", error=str(e))
            raise ConnectionError(f"Alpaca connection failed: {e}")
    
    async def disconnect(self) -> None:
        """Close Alpaca connection."""
        if not self._connected:
            return
        
        # Alpaca SDK doesn't require explicit disconnect
        self._trading_client = None
        self._data_client = None
        self._connected = False
        self._fill_callbacks.clear()
        
        self.logger.info("Disconnected from Alpaca")
    
    async def is_connected(self) -> bool:
        """Check if connected to Alpaca."""
        if not self._connected or self._trading_client is None:
            return False
        
        try:
            # Verify connection is still alive
            self._trading_client.get_account()
            return True
        except Exception:
            self._connected = False
            return False
    
    async def get_positions(self) -> list[Position]:
        """Get all current positions."""
        self._ensure_connected()
        
        try:
            alpaca_positions = self._trading_client.get_all_positions()
            
            positions = []
            for pos in alpaca_positions:
                positions.append(Position(
                    symbol=pos.symbol,
                    side=PositionSide.LONG if float(pos.qty) > 0 else PositionSide.SHORT,
                    quantity=Decimal(str(abs(float(pos.qty)))),
                    average_entry_price=Decimal(str(pos.avg_entry_price)),
                    market_value=Decimal(str(pos.market_value)),
                    unrealized_pnl=Decimal(str(pos.unrealized_pl)),
                    current_price=Decimal(str(pos.current_price))
                ))
            
            return positions
            
        except Exception as e:
            self.logger.error("Failed to get positions", error=str(e))
            raise
    
    async def get_account_summary(self) -> AccountSummary:
        """Get account summary."""
        self._ensure_connected()
        
        try:
            account = self._trading_client.get_account()
            
            return AccountSummary(
                account_id=account.id,
                equity=Decimal(str(account.equity)),
                cash=Decimal(str(account.cash)),
                buying_power=Decimal(str(account.buying_power)),
                portfolio_value=Decimal(str(account.portfolio_value)),
                currency=account.currency
            )
            
        except Exception as e:
            self.logger.error("Failed to get account summary", error=str(e))
            raise
    
    async def place_order(self, order: OrderRequest) -> str:
        """Place an order with Alpaca."""
        self._ensure_connected()
        
        try:
            # Convert our order types to Alpaca's
            side = AlpacaSide.BUY if order.side == OrderSide.BUY else AlpacaSide.SELL
            
            # Map time in force
            tif_map = {
                "DAY": TimeInForce.DAY,
                "GTC": TimeInForce.GTC,
                "IOC": TimeInForce.IOC,
                "FOK": TimeInForce.FOK,
            }
            time_in_force = tif_map.get(order.time_in_force, TimeInForce.DAY)
            
            # Create order request based on type
            if order.order_type == OrderType.MARKET:
                alpaca_order = MarketOrderRequest(
                    symbol=order.symbol,
                    qty=float(order.quantity),
                    side=side,
                    time_in_force=time_in_force
                )
            elif order.order_type == OrderType.LIMIT:
                alpaca_order = LimitOrderRequest(
                    symbol=order.symbol,
                    qty=float(order.quantity),
                    side=side,
                    time_in_force=time_in_force,
                    limit_price=float(order.limit_price)
                )
            elif order.order_type == OrderType.STOP_LIMIT:
                alpaca_order = StopLimitOrderRequest(
                    symbol=order.symbol,
                    qty=float(order.quantity),
                    side=side,
                    time_in_force=time_in_force,
                    limit_price=float(order.limit_price),
                    stop_price=float(order.stop_price)
                )
            else:
                raise ValueError(f"Unsupported order type: {order.order_type}")
            
            # Submit order
            response = self._trading_client.submit_order(alpaca_order)
            
            self.logger.info(
                "Order placed",
                broker_order_id=response.id,
                symbol=order.symbol,
                side=order.side.value,
                type=order.order_type.value,
                quantity=float(order.quantity)
            )
            
            return response.id
            
        except Exception as e:
            self.logger.error(
                "Failed to place order",
                symbol=order.symbol,
                error=str(e)
            )
            raise
    
    async def cancel_order(self, broker_order_id: str) -> None:
        """Cancel an order."""
        self._ensure_connected()
        
        try:
            self._trading_client.cancel_order_by_id(broker_order_id)
            self.logger.info("Order cancelled", broker_order_id=broker_order_id)
            
        except Exception as e:
            self.logger.error(
                "Failed to cancel order",
                broker_order_id=broker_order_id,
                error=str(e)
            )
            raise
    
    async def get_order(self, broker_order_id: str) -> Order:
        """Get order details."""
        self._ensure_connected()
        
        try:
            alpaca_order = self._trading_client.get_order_by_id(broker_order_id)
            
            # Map Alpaca status to our status
            status_map = {
                AlpacaStatus.NEW: OrderStatus.PENDING,
                AlpacaStatus.ACCEPTED: OrderStatus.SUBMITTED,
                AlpacaStatus.FILLED: OrderStatus.FILLED,
                AlpacaStatus.PARTIALLY_FILLED: OrderStatus.PARTIAL,
                AlpacaStatus.CANCELED: OrderStatus.CANCELLED,
                AlpacaStatus.EXPIRED: OrderStatus.CANCELLED,
                AlpacaStatus.REJECTED: OrderStatus.REJECTED,
                AlpacaStatus.PENDING_NEW: OrderStatus.PENDING,
                AlpacaStatus.PENDING_CANCEL: OrderStatus.SUBMITTED,
            }
            
            # Map order type
            type_map = {
                AlpacaType.MARKET: OrderType.MARKET,
                AlpacaType.LIMIT: OrderType.LIMIT,
                AlpacaType.STOP: OrderType.STOP,
                AlpacaType.STOP_LIMIT: OrderType.STOP_LIMIT,
            }
            
            return Order(
                broker_order_id=alpaca_order.id,
                symbol=alpaca_order.symbol,
                side=OrderSide.BUY if alpaca_order.side == AlpacaSide.BUY else OrderSide.SELL,
                order_type=type_map.get(alpaca_order.type, OrderType.MARKET),
                quantity=Decimal(str(alpaca_order.qty)),
                limit_price=Decimal(str(alpaca_order.limit_price)) if alpaca_order.limit_price else None,
                stop_price=Decimal(str(alpaca_order.stop_price)) if alpaca_order.stop_price else None,
                status=status_map.get(alpaca_order.status, OrderStatus.ERROR),
                filled_quantity=Decimal(str(alpaca_order.filled_qty)) if alpaca_order.filled_qty else Decimal("0"),
                average_fill_price=Decimal(str(alpaca_order.filled_avg_price)) if alpaca_order.filled_avg_price else None,
                created_at=alpaca_order.created_at,
                updated_at=alpaca_order.updated_at
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to get order",
                broker_order_id=broker_order_id,
                error=str(e)
            )
            raise
    
    async def get_market_data(
        self,
        symbol: str,
        duration: str = "1D",
        bar_size: str = "5min"
    ) -> pd.DataFrame:
        """Get historical market data."""
        self._ensure_connected()
        
        try:
            # Parse duration (e.g., "1D", "5D", "1M")
            duration_map = {
                "1D": timedelta(days=1),
                "5D": timedelta(days=5),
                "1W": timedelta(weeks=1),
                "1M": timedelta(days=30),
                "3M": timedelta(days=90),
            }
            time_delta = duration_map.get(duration, timedelta(days=1))
            start_time = datetime.now() - time_delta
            
            # Map bar size to TimeFrame
            timeframe_map = {
                "1min": TimeFrame.Minute,
                "5min": TimeFrame(5, "Min"),
                "15min": TimeFrame(15, "Min"),
                "1hour": TimeFrame.Hour,
                "1day": TimeFrame.Day,
            }
            timeframe = timeframe_map.get(bar_size, TimeFrame(5, "Min"))
            
            # Fetch bars
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=timeframe,
                start=start_time
            )
            
            bars = self._data_client.get_stock_bars(request)
            
            # Convert to DataFrame
            df = bars.df
            
            # Reset index to get timestamp as column
            if not df.empty:
                df = df.reset_index()
                df = df.rename(columns={
                    'timestamp': 'timestamp',
                    'open': 'open',
                    'high': 'high',
                    'low': 'low',
                    'close': 'close',
                    'volume': 'volume'
                })
                
                # Keep only required columns
                df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            return df
            
        except Exception as e:
            self.logger.error(
                "Failed to get market data",
                symbol=symbol,
                error=str(e)
            )
            raise
    
    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current market price."""
        self._ensure_connected()
        
        try:
            # Try to get from latest trade
            latest_trade = self._data_client.get_stock_latest_trade({symbol})
            if symbol in latest_trade:
                return Decimal(str(latest_trade[symbol].price))
            
            # Fallback: get from bars
            df = await self.get_market_data(symbol, duration="1D", bar_size="1min")
            if not df.empty:
                return Decimal(str(df.iloc[-1]['close']))
            
            raise ValueError(f"No price data available for {symbol}")
            
        except Exception as e:
            self.logger.error(
                "Failed to get current price",
                symbol=symbol,
                error=str(e)
            )
            raise
    
    def on_fill(self, callback: Callable[[Execution], None]) -> None:
        """
        Register callback for order fills.
        
        Note: Alpaca doesn't provide real-time fill notifications via SDK.
        Executor must poll get_order() for status changes.
        """
        self._fill_callbacks.append(callback)
        self.logger.info("Fill callback registered (polling required)")
    
    def _ensure_connected(self):
        """Raise error if not connected."""
        if not self._connected or self._trading_client is None:
            raise ConnectionError("Not connected to Alpaca. Call connect() first.")
    
    async def check_fills(self):
        """
        Poll for order fills and trigger callbacks.
        
        This should be called periodically by the executor since Alpaca
        doesn't provide real-time websocket fills in the basic SDK.
        """
        if not self._fill_callbacks:
            return
        
        try:
            # Get all orders from today
            orders = self._trading_client.get_orders(status="all")
            
            for alpaca_order in orders:
                if alpaca_order.status == AlpacaStatus.FILLED:
                    # Create execution for callbacks
                    execution = Execution(
                        broker_exec_id=alpaca_order.id,
                        broker_order_id=alpaca_order.id,
                        symbol=alpaca_order.symbol,
                        side=OrderSide.BUY if alpaca_order.side == AlpacaSide.BUY else OrderSide.SELL,
                        price=Decimal(str(alpaca_order.filled_avg_price)),
                        quantity=Decimal(str(alpaca_order.filled_qty)),
                        commission=Decimal("0"),  # Alpaca commission-free
                        executed_at=alpaca_order.filled_at or alpaca_order.updated_at
                    )
                    
                    # Trigger callbacks
                    for callback in self._fill_callbacks:
                        try:
                            callback(execution)
                        except Exception as e:
                            self.logger.error(
                                "Fill callback error",
                                error=str(e)
                            )
        
        except Exception as e:
            self.logger.error("Failed to check fills", error=str(e))
