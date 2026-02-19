"""
Test Broker Abstraction Layer

Tests for Phase 2 broker interface, implementations, and error handling.
Validates that all brokers comply with the abstract interface and handle
edge cases properly.
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import pandas as pd

# Will be uncommented as implementation lands:
# from ironhand.brokers.base import BrokerInterface, OrderRequest, Position, AccountSummary, Execution
# from ironhand.brokers.alpaca import AlpacaBroker
# from ironhand.brokers.paper import PaperBroker
# from ironhand.exceptions import BrokerConnectionError, OrderRejectedError, BrokerTimeoutError


pytestmark = pytest.mark.asyncio


# ============================================================================
# Abstract Interface Compliance Tests
# ============================================================================


class TestBrokerInterfaceCompliance:
    """
    Verify all broker implementations comply with BrokerInterface.
    
    Critical: All methods must be async and match the abstract signature.
    """
    
    @pytest.mark.skip("Waiting for brokers.base implementation")
    async def test_alpaca_implements_interface(self):
        """AlpacaBroker must implement all abstract methods."""
        from ironhand.brokers.base import BrokerInterface
        from ironhand.brokers.alpaca import AlpacaBroker
        
        assert issubclass(AlpacaBroker, BrokerInterface)
        
        # Check all abstract methods are implemented
        required_methods = [
            'connect', 'disconnect', 'get_positions', 'get_account_summary',
            'place_order', 'cancel_order', 'get_market_data', 'on_fill'
        ]
        
        for method_name in required_methods:
            assert hasattr(AlpacaBroker, method_name), f"Missing method: {method_name}"
            method = getattr(AlpacaBroker, method_name)
            # Verify it's not the abstract placeholder
            assert method is not getattr(BrokerInterface, method_name)
    
    @pytest.mark.skip("Waiting for brokers.paper implementation")
    async def test_paper_implements_interface(self):
        """PaperBroker must implement all abstract methods."""
        from ironhand.brokers.base import BrokerInterface
        from ironhand.brokers.paper import PaperBroker
        
        assert issubclass(PaperBroker, BrokerInterface)
        
        required_methods = [
            'connect', 'disconnect', 'get_positions', 'get_account_summary',
            'place_order', 'cancel_order', 'get_market_data', 'on_fill'
        ]
        
        for method_name in required_methods:
            assert hasattr(PaperBroker, method_name), f"Missing method: {method_name}"
    
    @pytest.mark.skip("Waiting for brokers.base implementation")
    async def test_cannot_instantiate_abstract_interface(self):
        """BrokerInterface itself should not be instantiable."""
        from ironhand.brokers.base import BrokerInterface
        
        with pytest.raises(TypeError):
            BrokerInterface()


# ============================================================================
# Alpaca Broker Tests (Mock the SDK)
# ============================================================================


class TestAlpacaBroker:
    """
    Test Alpaca broker implementation.
    
    Uses mocks to avoid real API calls. Validates connection, orders,
    positions, market data, and error handling.
    """
    
    @pytest.fixture
    async def mock_alpaca_client(self):
        """Mock Alpaca SDK client."""
        with patch('ironhand.brokers.alpaca.tradeapi') as mock_api:
            client = MagicMock()
            mock_api.REST.return_value = client
            yield client
    
    @pytest.fixture
    async def alpaca_broker(self, mock_alpaca_client):
        """Alpaca broker with mocked SDK."""
        # TODO: Uncomment when implementation exists
        # from ironhand.brokers.alpaca import AlpacaBroker
        # broker = AlpacaBroker(
        #     api_key="test_key",
        #     api_secret="test_secret",
        #     base_url="https://paper-api.alpaca.markets"
        # )
        # return broker
        pytest.skip("Waiting for brokers.alpaca implementation")
    
    @pytest.mark.skip("Waiting for brokers.alpaca implementation")
    async def test_connect_success(self, alpaca_broker, mock_alpaca_client):
        """Connection should verify API credentials."""
        mock_alpaca_client.get_account.return_value = MagicMock(
            status='ACTIVE',
            buying_power=10000.0
        )
        
        await alpaca_broker.connect()
        
        mock_alpaca_client.get_account.assert_called_once()
        assert alpaca_broker.is_connected
    
    @pytest.mark.skip("Waiting for brokers.alpaca implementation")
    async def test_connect_invalid_credentials(self, alpaca_broker, mock_alpaca_client):
        """Invalid credentials should raise BrokerConnectionError."""
        from ironhand.exceptions import BrokerConnectionError
        
        mock_alpaca_client.get_account.side_effect = Exception("Invalid API key")
        
        with pytest.raises(BrokerConnectionError, match="Invalid API key"):
            await alpaca_broker.connect()
    
    @pytest.mark.skip("Waiting for brokers.alpaca implementation")
    async def test_disconnect_clean(self, alpaca_broker):
        """Disconnect should clean up resources."""
        await alpaca_broker.connect()
        await alpaca_broker.disconnect()
        
        assert not alpaca_broker.is_connected
    
    @pytest.mark.skip("Waiting for brokers.alpaca implementation")
    async def test_place_order_limit(self, alpaca_broker, mock_alpaca_client):
        """Place limit order should return broker order ID."""
        from ironhand.brokers.base import OrderRequest
        
        mock_alpaca_client.submit_order.return_value = MagicMock(id="order_123")
        
        request = OrderRequest(
            symbol="ETHU",
            side="BUY",
            quantity=Decimal("10"),
            order_type="LMT",
            limit_price=Decimal("100.50")
        )
        
        order_id = await alpaca_broker.place_order(request)
        
        assert order_id == "order_123"
        mock_alpaca_client.submit_order.assert_called_once()
        call_kwargs = mock_alpaca_client.submit_order.call_args[1]
        assert call_kwargs['symbol'] == "ETHU"
        assert call_kwargs['qty'] == 10
        assert call_kwargs['side'] == "buy"
        assert call_kwargs['type'] == "limit"
        assert float(call_kwargs['limit_price']) == 100.50
    
    @pytest.mark.skip("Waiting for brokers.alpaca implementation")
    async def test_place_order_market(self, alpaca_broker, mock_alpaca_client):
        """Market orders should not have limit_price."""
        from ironhand.brokers.base import OrderRequest
        
        mock_alpaca_client.submit_order.return_value = MagicMock(id="order_456")
        
        request = OrderRequest(
            symbol="ETHU",
            side="SELL",
            quantity=Decimal("5"),
            order_type="MKT"
        )
        
        order_id = await alpaca_broker.place_order(request)
        
        assert order_id == "order_456"
        call_kwargs = mock_alpaca_client.submit_order.call_args[1]
        assert call_kwargs['type'] == "market"
        assert 'limit_price' not in call_kwargs
    
    @pytest.mark.skip("Waiting for brokers.alpaca implementation")
    async def test_place_order_rejected(self, alpaca_broker, mock_alpaca_client):
        """Rejected orders should raise OrderRejectedError."""
        from ironhand.brokers.base import OrderRequest
        from ironhand.exceptions import OrderRejectedError
        
        mock_alpaca_client.submit_order.side_effect = Exception("Insufficient buying power")
        
        request = OrderRequest(
            symbol="ETHU",
            side="BUY",
            quantity=Decimal("1000000"),
            order_type="MKT"
        )
        
        with pytest.raises(OrderRejectedError, match="Insufficient buying power"):
            await alpaca_broker.place_order(request)
    
    @pytest.mark.skip("Waiting for brokers.alpaca implementation")
    async def test_cancel_order_success(self, alpaca_broker, mock_alpaca_client):
        """Cancel order should succeed for pending orders."""
        mock_alpaca_client.cancel_order.return_value = None
        
        await alpaca_broker.cancel_order("order_123")
        
        mock_alpaca_client.cancel_order.assert_called_once_with("order_123")
    
    @pytest.mark.skip("Waiting for brokers.alpaca implementation")
    async def test_cancel_order_not_found(self, alpaca_broker, mock_alpaca_client):
        """Canceling non-existent order should raise appropriate error."""
        from ironhand.exceptions import OrderNotFoundError
        
        mock_alpaca_client.cancel_order.side_effect = Exception("Order not found")
        
        with pytest.raises(OrderNotFoundError):
            await alpaca_broker.cancel_order("nonexistent")
    
    @pytest.mark.skip("Waiting for brokers.alpaca implementation")
    async def test_get_positions(self, alpaca_broker, mock_alpaca_client):
        """Get positions should return list of Position objects."""
        from ironhand.brokers.base import Position
        
        mock_alpaca_client.list_positions.return_value = [
            MagicMock(
                symbol="ETHU",
                qty="10",
                avg_entry_price="100.50",
                side="long",
                unrealized_pl="50.00"
            ),
            MagicMock(
                symbol="BTCU",
                qty="2",
                avg_entry_price="50000.00",
                side="long",
                unrealized_pl="-100.00"
            )
        ]
        
        positions = await alpaca_broker.get_positions()
        
        assert len(positions) == 2
        assert all(isinstance(p, Position) for p in positions)
        assert positions[0].symbol == "ETHU"
        assert positions[0].quantity == Decimal("10")
        assert positions[0].entry_price == Decimal("100.50")
    
    @pytest.mark.skip("Waiting for brokers.alpaca implementation")
    async def test_get_account_summary(self, alpaca_broker, mock_alpaca_client):
        """Get account summary should return AccountSummary object."""
        from ironhand.brokers.base import AccountSummary
        
        mock_alpaca_client.get_account.return_value = MagicMock(
            cash="10000.00",
            portfolio_value="15000.00",
            buying_power="20000.00"
        )
        
        summary = await alpaca_broker.get_account_summary()
        
        assert isinstance(summary, AccountSummary)
        assert summary.cash == Decimal("10000.00")
        assert summary.portfolio_value == Decimal("15000.00")
        assert summary.buying_power == Decimal("20000.00")
    
    @pytest.mark.skip("Waiting for brokers.alpaca implementation")
    async def test_get_market_data(self, alpaca_broker, mock_alpaca_client):
        """Market data should return pandas DataFrame with OHLCV."""
        # Mock Alpaca bars response
        mock_bars = pd.DataFrame({
            'timestamp': pd.date_range(end=datetime.now(timezone.utc), periods=100, freq='1min'),
            'open': [100 + i*0.1 for i in range(100)],
            'high': [100.5 + i*0.1 for i in range(100)],
            'low': [99.5 + i*0.1 for i in range(100)],
            'close': [100.2 + i*0.1 for i in range(100)],
            'volume': [1000 + i*10 for i in range(100)]
        })
        
        mock_alpaca_client.get_bars.return_value = mock_bars
        
        df = await alpaca_broker.get_market_data("ETHU", duration="1D")
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 100
        assert all(col in df.columns for col in ['open', 'high', 'low', 'close', 'volume'])
    
    @pytest.mark.skip("Waiting for brokers.alpaca implementation")
    async def test_on_fill_callback(self, alpaca_broker):
        """Fill callback should be triggered when order fills."""
        from ironhand.brokers.base import Execution
        
        fill_received = []
        
        def on_fill(execution: Execution):
            fill_received.append(execution)
        
        alpaca_broker.on_fill(on_fill)
        
        # Simulate fill event
        await alpaca_broker._handle_fill({
            'order_id': 'order_123',
            'symbol': 'ETHU',
            'qty': '10',
            'price': '100.50'
        })
        
        assert len(fill_received) == 1
        assert fill_received[0].symbol == 'ETHU'
        assert fill_received[0].quantity == Decimal('10')
        assert fill_received[0].price == Decimal('100.50')


# ============================================================================
# Paper Broker Tests
# ============================================================================


class TestPaperBroker:
    """
    Test paper trading implementation.
    
    Paper broker simulates fills locally without real broker connection.
    """
    
    @pytest.fixture
    def paper_broker(self):
        """Paper broker instance."""
        # TODO: Uncomment when implementation exists
        # from ironhand.brokers.paper import PaperBroker
        # return PaperBroker(initial_cash=Decimal("10000"))
        pytest.skip("Waiting for brokers.paper implementation")
    
    @pytest.mark.skip("Waiting for brokers.paper implementation")
    async def test_connect_instant(self, paper_broker):
        """Paper broker connection is instant (no external service)."""
        await paper_broker.connect()
        assert paper_broker.is_connected
    
    @pytest.mark.skip("Waiting for brokers.paper implementation")
    async def test_place_order_updates_positions(self, paper_broker):
        """Paper broker should simulate fills and update positions."""
        from ironhand.brokers.base import OrderRequest
        
        await paper_broker.connect()
        
        request = OrderRequest(
            symbol="ETHU",
            side="BUY",
            quantity=Decimal("10"),
            order_type="MKT"
        )
        
        # Provide simulated market price
        await paper_broker.set_market_price("ETHU", Decimal("100.00"))
        
        order_id = await paper_broker.place_order(request)
        
        # Order should fill immediately in paper trading
        positions = await paper_broker.get_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "ETHU"
        assert positions[0].quantity == Decimal("10")
    
    @pytest.mark.skip("Waiting for brokers.paper implementation")
    async def test_account_cash_decreases_on_buy(self, paper_broker):
        """Buying should decrease available cash."""
        from ironhand.brokers.base import OrderRequest
        
        await paper_broker.connect()
        initial_summary = await paper_broker.get_account_summary()
        initial_cash = initial_summary.cash
        
        await paper_broker.set_market_price("ETHU", Decimal("100.00"))
        
        request = OrderRequest(
            symbol="ETHU",
            side="BUY",
            quantity=Decimal("10"),
            order_type="MKT"
        )
        
        await paper_broker.place_order(request)
        
        new_summary = await paper_broker.get_account_summary()
        expected_cash = initial_cash - (Decimal("10") * Decimal("100.00"))
        assert new_summary.cash == expected_cash
    
    @pytest.mark.skip("Waiting for brokers.paper implementation")
    async def test_insufficient_funds_rejected(self, paper_broker):
        """Orders exceeding cash should be rejected."""
        from ironhand.brokers.base import OrderRequest
        from ironhand.exceptions import OrderRejectedError
        
        await paper_broker.connect()
        await paper_broker.set_market_price("ETHU", Decimal("100.00"))
        
        # Try to buy more than we have cash for
        request = OrderRequest(
            symbol="ETHU",
            side="BUY",
            quantity=Decimal("1000000"),
            order_type="MKT"
        )
        
        with pytest.raises(OrderRejectedError, match="Insufficient funds"):
            await paper_broker.place_order(request)


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestBrokerErrorHandling:
    """
    Test error scenarios across all brokers.
    
    Connection failures, timeouts, rejected orders, etc.
    """
    
    @pytest.mark.skip("Waiting for brokers.alpaca implementation")
    async def test_connection_timeout(self):
        """Connection timeout should raise BrokerTimeoutError."""
        from ironhand.brokers.alpaca import AlpacaBroker
        from ironhand.exceptions import BrokerTimeoutError
        
        with patch('ironhand.brokers.alpaca.tradeapi') as mock_api:
            mock_api.REST.side_effect = TimeoutError("Connection timed out")
            
            broker = AlpacaBroker(api_key="test", api_secret="test")
            
            with pytest.raises(BrokerTimeoutError):
                await broker.connect()
    
    @pytest.mark.skip("Waiting for brokers.alpaca implementation")
    async def test_network_error_during_order(self, alpaca_broker, mock_alpaca_client):
        """Network errors should be retried with exponential backoff."""
        from ironhand.brokers.base import OrderRequest
        from ironhand.exceptions import BrokerConnectionError
        
        # Fail first 2 attempts, succeed on 3rd
        mock_alpaca_client.submit_order.side_effect = [
            ConnectionError("Network error"),
            ConnectionError("Network error"),
            MagicMock(id="order_123")
        ]
        
        request = OrderRequest(
            symbol="ETHU",
            side="BUY",
            quantity=Decimal("10"),
            order_type="MKT"
        )
        
        order_id = await alpaca_broker.place_order(request)
        
        assert order_id == "order_123"
        assert mock_alpaca_client.submit_order.call_count == 3
    
    @pytest.mark.skip("Waiting for brokers.alpaca implementation")
    async def test_max_retries_exceeded(self, alpaca_broker, mock_alpaca_client):
        """After max retries, should raise BrokerConnectionError."""
        from ironhand.brokers.base import OrderRequest
        from ironhand.exceptions import BrokerConnectionError
        
        mock_alpaca_client.submit_order.side_effect = ConnectionError("Network error")
        
        request = OrderRequest(
            symbol="ETHU",
            side="BUY",
            quantity=Decimal("10"),
            order_type="MKT"
        )
        
        with pytest.raises(BrokerConnectionError):
            await alpaca_broker.place_order(request, max_retries=3)


# ============================================================================
# Integration Smoke Tests
# ============================================================================


class TestBrokerIntegration:
    """
    Light integration tests (still mocked, but test full workflows).
    """
    
    @pytest.mark.skip("Waiting for full broker implementation")
    async def test_buy_sell_workflow(self, alpaca_broker, mock_alpaca_client):
        """Full workflow: connect → buy → hold → sell → disconnect."""
        from ironhand.brokers.base import OrderRequest
        
        # Setup mocks
        mock_alpaca_client.get_account.return_value = MagicMock(
            status='ACTIVE',
            cash="10000"
        )
        mock_alpaca_client.submit_order.side_effect = [
            MagicMock(id="buy_order"),
            MagicMock(id="sell_order")
        ]
        mock_alpaca_client.list_positions.return_value = [
            MagicMock(
                symbol="ETHU",
                qty="10",
                avg_entry_price="100.00",
                side="long"
            )
        ]
        
        # Workflow
        await alpaca_broker.connect()
        
        # Buy
        buy_request = OrderRequest(
            symbol="ETHU",
            side="BUY",
            quantity=Decimal("10"),
            order_type="MKT"
        )
        buy_order_id = await alpaca_broker.place_order(buy_request)
        assert buy_order_id == "buy_order"
        
        # Check positions
        positions = await alpaca_broker.get_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "ETHU"
        
        # Sell
        sell_request = OrderRequest(
            symbol="ETHU",
            side="SELL",
            quantity=Decimal("10"),
            order_type="MKT"
        )
        sell_order_id = await alpaca_broker.place_order(sell_request)
        assert sell_order_id == "sell_order"
        
        await alpaca_broker.disconnect()
        assert not alpaca_broker.is_connected
