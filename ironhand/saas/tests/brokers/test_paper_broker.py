"""
Tests for brokers/paper.py - Paper trading broker implementation.

Tests the paper trading fill simulation, account management,
and order lifecycle without real money.

This broker is critical for testing and demo accounts.
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime


try:
    from ironhand.brokers.paper import PaperBroker
except ImportError:
    PaperBroker = None


pytestmark = pytest.mark.skipif(
    PaperBroker is None,
    reason="PaperBroker not implemented yet"
)


class TestPaperBrokerBasics:
    """Test basic paper broker functionality."""
    
    @pytest.mark.asyncio
    async def test_paper_broker_initialization(self):
        """Paper broker should initialize with default values."""
        broker = PaperBroker(config={
            'initial_cash': 100000.0
        })
        
        await broker.connect()
        
        summary = await broker.get_account_summary()
        assert summary['cash'] == 100000.0
        assert summary['net_liquidation'] == 100000.0
        
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_no_real_connection_required(self):
        """Paper broker should work without external connections."""
        broker = PaperBroker(config={'initial_cash': 50000.0})
        
        # Connect should succeed immediately
        await broker.connect()
        assert broker.connected
        
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_multiple_connect_disconnect_cycles(self):
        """Should handle multiple connect/disconnect cycles."""
        broker = PaperBroker(config={'initial_cash': 100000.0})
        
        for _ in range(3):
            await broker.connect()
            assert broker.connected
            await broker.disconnect()
            assert not broker.connected


class TestPaperTradingExecution:
    """Test order placement and execution."""
    
    @pytest.mark.asyncio
    async def test_place_limit_order(self):
        """Place a limit order."""
        broker = PaperBroker(config={'initial_cash': 100000.0})
        await broker.connect()
        
        order = {
            'symbol': 'ETHU',
            'side': 'BUY',
            'quantity': 100,
            'order_type': 'LMT',
            'limit_price': 50.0
        }
        
        order_id = await broker.place_order(order)
        
        assert order_id is not None
        assert isinstance(order_id, str)
        assert len(order_id) > 0
        
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_place_market_order(self):
        """Place a market order."""
        broker = PaperBroker(config={'initial_cash': 100000.0})
        await broker.connect()
        
        # Set current market price
        broker.set_market_price('ETHU', 50.0)
        
        order = {
            'symbol': 'ETHU',
            'side': 'BUY',
            'quantity': 100,
            'order_type': 'MKT'
        }
        
        order_id = await broker.place_order(order)
        assert order_id is not None
        
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_order_fill_simulation(self):
        """Test that orders are filled when price is reached."""
        broker = PaperBroker(config={'initial_cash': 100000.0})
        await broker.connect()
        
        fills_received = []
        
        def on_fill(execution):
            fills_received.append(execution)
        
        broker.on_fill(on_fill)
        
        # Place limit buy at $50
        order = {
            'symbol': 'ETHU',
            'side': 'BUY',
            'quantity': 100,
            'order_type': 'LMT',
            'limit_price': 50.0
        }
        
        order_id = await broker.place_order(order)
        
        # Set market price to $50 (should fill)
        broker.set_market_price('ETHU', 50.0)
        await broker.process_pending_orders()
        
        # Should have received fill
        assert len(fills_received) == 1
        assert fills_received[0]['price'] == 50.0
        assert fills_received[0]['quantity'] == 100
        
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_limit_order_not_filled_above_price(self):
        """Limit buy should not fill above limit price."""
        broker = PaperBroker(config={'initial_cash': 100000.0})
        await broker.connect()
        
        fills_received = []
        broker.on_fill(lambda e: fills_received.append(e))
        
        # Place limit buy at $50
        order = {
            'symbol': 'ETHU',
            'side': 'BUY',
            'quantity': 100,
            'order_type': 'LMT',
            'limit_price': 50.0
        }
        
        await broker.place_order(order)
        
        # Market price is $51 (above limit)
        broker.set_market_price('ETHU', 51.0)
        await broker.process_pending_orders()
        
        # Should NOT fill
        assert len(fills_received) == 0
        
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_limit_sell_fills_at_or_above_price(self):
        """Limit sell should fill at or above limit price."""
        broker = PaperBroker(config={'initial_cash': 100000.0})
        await broker.connect()
        
        # First, buy to create position
        broker.add_position('ETHU', 100, 45.0)
        
        fills_received = []
        broker.on_fill(lambda e: fills_received.append(e))
        
        # Place limit sell at $50
        order = {
            'symbol': 'ETHU',
            'side': 'SELL',
            'quantity': 100,
            'order_type': 'LMT',
            'limit_price': 50.0
        }
        
        await broker.place_order(order)
        
        # Market goes to $52 (above limit)
        broker.set_market_price('ETHU', 52.0)
        await broker.process_pending_orders()
        
        # Should fill at current price
        assert len(fills_received) == 1
        assert fills_received[0]['price'] >= 50.0
        
        await broker.disconnect()


class TestPaperAccountManagement:
    """Test account state management."""
    
    @pytest.mark.asyncio
    async def test_cash_deducted_on_buy(self):
        """Cash should decrease when buying."""
        broker = PaperBroker(config={'initial_cash': 100000.0})
        await broker.connect()
        
        initial_cash = (await broker.get_account_summary())['cash']
        
        # Buy $5000 worth
        broker.set_market_price('ETHU', 50.0)
        await broker.place_order({
            'symbol': 'ETHU',
            'side': 'BUY',
            'quantity': 100,
            'order_type': 'MKT'
        })
        
        # Process the fill
        await broker.process_pending_orders()
        
        final_cash = (await broker.get_account_summary())['cash']
        
        # Cash should be reduced by ~$5000
        assert final_cash < initial_cash
        assert abs((initial_cash - final_cash) - 5000.0) < 100
        
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_cash_increased_on_sell(self):
        """Cash should increase when selling."""
        broker = PaperBroker(config={'initial_cash': 100000.0})
        await broker.connect()
        
        # Start with a position
        broker.add_position('ETHU', 100, 45.0)
        
        initial_cash = (await broker.get_account_summary())['cash']
        
        # Sell at $50
        broker.set_market_price('ETHU', 50.0)
        await broker.place_order({
            'symbol': 'ETHU',
            'side': 'SELL',
            'quantity': 100,
            'order_type': 'MKT'
        })
        
        await broker.process_pending_orders()
        
        final_cash = (await broker.get_account_summary())['cash']
        
        # Cash should increase by $5000
        assert final_cash > initial_cash
        assert abs((final_cash - initial_cash) - 5000.0) < 100
        
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_position_created_on_buy(self):
        """Position should be created after buy fills."""
        broker = PaperBroker(config={'initial_cash': 100000.0})
        await broker.connect()
        
        broker.set_market_price('ETHU', 50.0)
        await broker.place_order({
            'symbol': 'ETHU',
            'side': 'BUY',
            'quantity': 100,
            'order_type': 'MKT'
        })
        
        await broker.process_pending_orders()
        
        positions = await broker.get_positions()
        
        assert len(positions) == 1
        assert positions[0]['symbol'] == 'ETHU'
        assert positions[0]['quantity'] == 100
        
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_position_reduced_on_partial_sell(self):
        """Position should reduce after partial sell."""
        broker = PaperBroker(config={'initial_cash': 100000.0})
        await broker.connect()
        
        # Start with 100 shares
        broker.add_position('ETHU', 100, 45.0)
        
        # Sell 30 shares
        broker.set_market_price('ETHU', 50.0)
        await broker.place_order({
            'symbol': 'ETHU',
            'side': 'SELL',
            'quantity': 30,
            'order_type': 'MKT'
        })
        
        await broker.process_pending_orders()
        
        positions = await broker.get_positions()
        
        assert len(positions) == 1
        assert positions[0]['quantity'] == 70
        
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_position_removed_on_full_sell(self):
        """Position should be removed after selling all."""
        broker = PaperBroker(config={'initial_cash': 100000.0})
        await broker.connect()
        
        broker.add_position('ETHU', 100, 45.0)
        
        # Sell all 100 shares
        broker.set_market_price('ETHU', 50.0)
        await broker.place_order({
            'symbol': 'ETHU',
            'side': 'SELL',
            'quantity': 100,
            'order_type': 'MKT'
        })
        
        await broker.process_pending_orders()
        
        positions = await broker.get_positions()
        
        # Position should be closed
        assert len(positions) == 0
        
        await broker.disconnect()


class TestPaperBrokerPnL:
    """Test P&L calculations."""
    
    @pytest.mark.asyncio
    async def test_realized_pnl_on_profitable_trade(self):
        """Calculate realized P&L on profitable trade."""
        broker = PaperBroker(config={'initial_cash': 100000.0})
        await broker.connect()
        
        # Buy at $45
        broker.set_market_price('ETHU', 45.0)
        await broker.place_order({
            'symbol': 'ETHU',
            'side': 'BUY',
            'quantity': 100,
            'order_type': 'MKT'
        })
        await broker.process_pending_orders()
        
        # Sell at $50
        broker.set_market_price('ETHU', 50.0)
        await broker.place_order({
            'symbol': 'ETHU',
            'side': 'SELL',
            'quantity': 100,
            'order_type': 'MKT'
        })
        await broker.process_pending_orders()
        
        # Realized P&L should be ~$500 (minus commissions)
        summary = await broker.get_account_summary()
        realized_pnl = summary.get('realized_pnl', 0)
        
        assert realized_pnl > 400  # Allow for commissions
        
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_unrealized_pnl_tracking(self):
        """Track unrealized P&L on open positions."""
        broker = PaperBroker(config={'initial_cash': 100000.0})
        await broker.connect()
        
        # Buy at $45
        broker.set_market_price('ETHU', 45.0)
        await broker.place_order({
            'symbol': 'ETHU',
            'side': 'BUY',
            'quantity': 100,
            'order_type': 'MKT'
        })
        await broker.process_pending_orders()
        
        # Price moves to $50
        broker.set_market_price('ETHU', 50.0)
        
        positions = await broker.get_positions()
        
        # Unrealized P&L should be ~$500
        assert positions[0]['unrealized_pnl'] == pytest.approx(500.0, abs=10)
        
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_net_liquidation_includes_positions(self):
        """Net liquidation should include position value."""
        broker = PaperBroker(config={'initial_cash': 100000.0})
        await broker.connect()
        
        # Buy $5000 worth
        broker.set_market_price('ETHU', 50.0)
        await broker.place_order({
            'symbol': 'ETHU',
            'side': 'BUY',
            'quantity': 100,
            'order_type': 'MKT'
        })
        await broker.process_pending_orders()
        
        summary = await broker.get_account_summary()
        
        # Net liq = cash + position value
        # Should still be ~$100k (assuming price hasn't moved)
        assert summary['net_liquidation'] == pytest.approx(100000.0, abs=100)
        
        # Price goes up to $55
        broker.set_market_price('ETHU', 55.0)
        summary = await broker.get_account_summary()
        
        # Net liq should increase by $500 (unrealized gain)
        assert summary['net_liquidation'] > 100000.0
        
        await broker.disconnect()


class TestPaperBrokerCommissions:
    """Test commission calculations."""
    
    @pytest.mark.asyncio
    async def test_commissions_deducted(self):
        """Commissions should be deducted from cash."""
        broker = PaperBroker(config={
            'initial_cash': 100000.0,
            'commission_per_share': 0.005
        })
        await broker.connect()
        
        initial_cash = (await broker.get_account_summary())['cash']
        
        # Buy 100 shares
        broker.set_market_price('ETHU', 50.0)
        await broker.place_order({
            'symbol': 'ETHU',
            'side': 'BUY',
            'quantity': 100,
            'order_type': 'MKT'
        })
        await broker.process_pending_orders()
        
        final_cash = (await broker.get_account_summary())['cash']
        
        # Should deduct $5000 + $0.50 commission
        expected_deduction = 5000.0 + (100 * 0.005)
        actual_deduction = initial_cash - final_cash
        
        assert actual_deduction == pytest.approx(expected_deduction, abs=0.1)
        
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_configurable_commission_model(self):
        """Should support different commission models."""
        # Per-share
        broker1 = PaperBroker(config={
            'initial_cash': 100000.0,
            'commission_model': 'per_share',
            'commission_per_share': 0.005
        })
        
        # Fixed per trade
        broker2 = PaperBroker(config={
            'initial_cash': 100000.0,
            'commission_model': 'fixed',
            'commission_fixed': 1.0
        })
        
        # Both should work
        await broker1.connect()
        await broker2.connect()
        
        await broker1.disconnect()
        await broker2.disconnect()


class TestPaperBrokerEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.mark.asyncio
    async def test_insufficient_cash_for_buy(self):
        """Should reject buy when insufficient cash."""
        broker = PaperBroker(config={'initial_cash': 1000.0})
        await broker.connect()
        
        broker.set_market_price('ETHU', 50.0)
        
        # Try to buy $10,000 worth (insufficient cash)
        with pytest.raises(Exception) as exc:
            await broker.place_order({
                'symbol': 'ETHU',
                'side': 'BUY',
                'quantity': 200,
                'order_type': 'MKT'
            })
        
        assert 'insufficient' in str(exc.value).lower()
        
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_cannot_sell_more_than_owned(self):
        """Should reject sell exceeding position size."""
        broker = PaperBroker(config={'initial_cash': 100000.0})
        await broker.connect()
        
        # Only have 100 shares
        broker.add_position('ETHU', 100, 45.0)
        
        # Try to sell 150
        broker.set_market_price('ETHU', 50.0)
        
        with pytest.raises(Exception):
            await broker.place_order({
                'symbol': 'ETHU',
                'side': 'SELL',
                'quantity': 150,
                'order_type': 'MKT'
            })
        
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_cancel_pending_order(self):
        """Should be able to cancel pending orders."""
        broker = PaperBroker(config={'initial_cash': 100000.0})
        await broker.connect()
        
        # Place limit order that won't fill immediately
        order_id = await broker.place_order({
            'symbol': 'ETHU',
            'side': 'BUY',
            'quantity': 100,
            'order_type': 'LMT',
            'limit_price': 45.0
        })
        
        # Market is at $50, won't fill
        broker.set_market_price('ETHU', 50.0)
        
        # Cancel the order
        await broker.cancel_order(order_id)
        
        # Process - should not fill
        await broker.process_pending_orders()
        
        positions = await broker.get_positions()
        assert len(positions) == 0
        
        await broker.disconnect()


class TestPaperBrokerRealism:
    """Test realistic market simulation features."""
    
    @pytest.mark.asyncio
    async def test_slippage_simulation(self):
        """Should simulate slippage on market orders."""
        broker = PaperBroker(config={
            'initial_cash': 100000.0,
            'slippage_pct': 0.1  # 0.1% slippage
        })
        await broker.connect()
        
        fills_received = []
        broker.on_fill(lambda e: fills_received.append(e))
        
        broker.set_market_price('ETHU', 50.0)
        
        # Place market buy
        await broker.place_order({
            'symbol': 'ETHU',
            'side': 'BUY',
            'quantity': 100,
            'order_type': 'MKT'
        })
        
        await broker.process_pending_orders()
        
        # Fill price should be slightly above 50.0 (slippage)
        assert fills_received[0]['price'] >= 50.0
        assert fills_received[0]['price'] <= 50.10  # 0.1% slippage
        
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_partial_fill_simulation(self):
        """Should simulate partial fills for large orders."""
        pytest.skip("Partial fills are optional advanced feature")
    
    @pytest.mark.asyncio
    async def test_order_latency_simulation(self):
        """Should simulate order processing latency."""
        pytest.skip("Latency simulation is optional advanced feature")
