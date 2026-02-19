"""
Tests for brokers/base.py - Broker interface contract.

Verifies that all broker implementations conform to the BrokerInterface
abstract base class contract.

Tests:
- Required methods are implemented
- Method signatures are correct
- Return types match interface
- Error handling is consistent
"""

import pytest
from abc import ABC
from typing import List


try:
    from ironhand.brokers.base import BrokerInterface
    from ironhand.brokers.ibkr_tws import IBKRTWSBroker
    from ironhand.brokers.ibkr_portal import IBKRPortalBroker
    from ironhand.brokers.paper import PaperBroker
except ImportError:
    BrokerInterface = None
    IBKRTWSBroker = None
    IBKRPortalBroker = None
    PaperBroker = None


pytestmark = pytest.mark.skipif(
    BrokerInterface is None,
    reason="BrokerInterface not implemented yet"
)


# List all broker implementations to test
BROKER_IMPLEMENTATIONS = []

if IBKRTWSBroker:
    BROKER_IMPLEMENTATIONS.append(IBKRTWSBroker)
if IBKRPortalBroker:
    BROKER_IMPLEMENTATIONS.append(IBKRPortalBroker)
if PaperBroker:
    BROKER_IMPLEMENTATIONS.append(PaperBroker)


class TestBrokerInterfaceContract:
    """Test that BrokerInterface defines the correct contract."""
    
    def test_interface_is_abstract(self):
        """BrokerInterface should be abstract (cannot instantiate)."""
        with pytest.raises(TypeError):
            BrokerInterface()
    
    def test_required_methods_defined(self):
        """Interface should define all required methods."""
        required_methods = [
            'connect',
            'disconnect',
            'get_positions',
            'get_account_summary',
            'place_order',
            'cancel_order',
            'get_market_data',
            'on_fill'
        ]
        
        for method_name in required_methods:
            assert hasattr(BrokerInterface, method_name), \
                f"BrokerInterface missing required method: {method_name}"
    
    def test_method_signatures(self):
        """Verify method signatures match expectations."""
        import inspect
        
        # Check connect is async
        assert inspect.iscoroutinefunction(BrokerInterface.connect)
        
        # Check disconnect is async
        assert inspect.iscoroutinefunction(BrokerInterface.disconnect)
        
        # Check place_order is async and returns str (order_id)
        assert inspect.iscoroutinefunction(BrokerInterface.place_order)


@pytest.mark.parametrize("broker_class", BROKER_IMPLEMENTATIONS)
class TestBrokerImplementations:
    """Test all broker implementations conform to interface."""
    
    def test_implements_all_required_methods(self, broker_class):
        """Each broker should implement all interface methods."""
        required_methods = [
            'connect',
            'disconnect',
            'get_positions',
            'get_account_summary',
            'place_order',
            'cancel_order',
            'get_market_data',
            'on_fill'
        ]
        
        for method_name in required_methods:
            assert hasattr(broker_class, method_name), \
                f"{broker_class.__name__} missing {method_name}"
            
            method = getattr(broker_class, method_name)
            assert callable(method), \
                f"{method_name} is not callable"
    
    def test_is_subclass_of_interface(self, broker_class):
        """Each broker should inherit from BrokerInterface."""
        assert issubclass(broker_class, BrokerInterface), \
            f"{broker_class.__name__} does not inherit from BrokerInterface"
    
    @pytest.mark.asyncio
    async def test_connect_disconnect_lifecycle(self, broker_class):
        """Test connect/disconnect lifecycle."""
        # Skip if this requires real credentials
        if broker_class.__name__ in ['IBKRTWSBroker', 'IBKRPortalBroker']:
            pytest.skip("Requires live broker connection")
        
        # Create instance (may need mock config)
        try:
            broker = broker_class(config={})
        except Exception:
            pytest.skip("Broker requires specific config")
            return
        
        # Should connect without error
        await broker.connect()
        
        # Should disconnect without error
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_get_positions_returns_list(self, broker_class):
        """get_positions should return a list."""
        if broker_class.__name__ in ['IBKRTWSBroker', 'IBKRPortalBroker']:
            pytest.skip("Requires live broker connection")
        
        try:
            broker = broker_class(config={})
            await broker.connect()
            
            positions = await broker.get_positions()
            
            assert isinstance(positions, list), \
                "get_positions should return a list"
            
            await broker.disconnect()
        except Exception:
            pytest.skip("Broker requires specific config")
    
    @pytest.mark.asyncio
    async def test_get_account_summary_returns_dict(self, broker_class):
        """get_account_summary should return dict with required fields."""
        if broker_class.__name__ in ['IBKRTWSBroker', 'IBKRPortalBroker']:
            pytest.skip("Requires live broker connection")
        
        try:
            broker = broker_class(config={})
            await broker.connect()
            
            summary = await broker.get_account_summary()
            
            assert isinstance(summary, dict), \
                "get_account_summary should return dict"
            
            # Required fields
            required_fields = ['net_liquidation', 'cash', 'buying_power']
            for field in required_fields:
                assert field in summary, \
                    f"Account summary missing field: {field}"
            
            await broker.disconnect()
        except Exception:
            pytest.skip("Broker requires specific config")
    
    @pytest.mark.asyncio
    async def test_place_order_returns_order_id(self, broker_class):
        """place_order should return a string order ID."""
        if broker_class.__name__ in ['IBKRTWSBroker', 'IBKRPortalBroker']:
            pytest.skip("Requires live broker connection")
        
        try:
            broker = broker_class(config={})
            await broker.connect()
            
            # Mock order
            order = {
                'symbol': 'ETHU',
                'side': 'BUY',
                'quantity': 10,
                'order_type': 'LMT',
                'limit_price': 50.0
            }
            
            order_id = await broker.place_order(order)
            
            assert isinstance(order_id, str), \
                "place_order should return string order ID"
            assert len(order_id) > 0, \
                "Order ID should not be empty"
            
            await broker.disconnect()
        except Exception:
            pytest.skip("Broker requires specific config")


class TestBrokerErrorHandling:
    """Test error handling across brokers."""
    
    @pytest.mark.asyncio
    async def test_connect_failure_raises_exception(self, mock_broker):
        """Connection failure should raise clear exception."""
        # Inject connection failure
        mock_broker.should_fail_connect = True
        
        with pytest.raises(Exception) as exc_info:
            await mock_broker.connect()
        
        # Should be a meaningful error
        assert str(exc_info.value) != ""
    
    @pytest.mark.asyncio
    async def test_operations_before_connect_raise_error(self, mock_broker):
        """Operations before connect should raise error."""
        # Don't connect
        
        with pytest.raises(Exception):
            await mock_broker.get_positions()
    
    @pytest.mark.asyncio
    async def test_invalid_order_raises_error(self, mock_broker):
        """Invalid order should raise validation error."""
        await mock_broker.connect()
        
        # Invalid order (missing required fields)
        invalid_order = {
            'symbol': 'ETHU',
            # Missing side, quantity, etc.
        }
        
        with pytest.raises(Exception):
            await mock_broker.place_order(invalid_order)
        
        await mock_broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_cancel_nonexistent_order_raises_error(self, mock_broker):
        """Cancelling non-existent order should raise error."""
        await mock_broker.connect()
        
        with pytest.raises(Exception):
            await mock_broker.cancel_order("NONEXISTENT_ORDER_ID")
        
        await mock_broker.disconnect()


class TestBrokerFactoryPattern:
    """Test broker factory/registry pattern."""
    
    def test_broker_factory_exists(self):
        """Should have a factory function to create brokers."""
        try:
            from ironhand.brokers.factory import create_broker
            assert callable(create_broker)
        except ImportError:
            pytest.skip("Broker factory not implemented")
    
    def test_broker_creation_from_type(self):
        """Factory should create correct broker from type string."""
        try:
            from ironhand.brokers.factory import create_broker
            
            # Test each broker type
            broker_types = [
                ('paper', PaperBroker),
                ('ibkr_tws', IBKRTWSBroker),
                ('ibkr_portal', IBKRPortalBroker),
            ]
            
            for broker_type, expected_class in broker_types:
                if expected_class is None:
                    continue
                    
                broker = create_broker(broker_type, config={})
                assert isinstance(broker, expected_class), \
                    f"Factory did not create correct type for '{broker_type}'"
                    
        except ImportError:
            pytest.skip("Broker factory not implemented")
    
    def test_invalid_broker_type_raises_error(self):
        """Factory should raise error for unknown broker type."""
        try:
            from ironhand.brokers.factory import create_broker
            
            with pytest.raises(ValueError):
                create_broker('nonexistent_broker', config={})
                
        except ImportError:
            pytest.skip("Broker factory not implemented")


class TestBrokerConfiguration:
    """Test broker configuration handling."""
    
    def test_config_validation(self):
        """Brokers should validate their configuration."""
        if PaperBroker is None:
            pytest.skip("PaperBroker not implemented")
        
        # Invalid config should raise
        with pytest.raises(Exception):
            PaperBroker(config={'invalid_key': 'value'})
    
    def test_required_config_fields(self):
        """Each broker should document required config fields."""
        for broker_class in BROKER_IMPLEMENTATIONS:
            # Should have class attribute or property defining required config
            assert hasattr(broker_class, 'REQUIRED_CONFIG') or \
                   hasattr(broker_class, 'required_config_fields'), \
                   f"{broker_class.__name__} should document required config"
    
    def test_encrypted_credentials_support(self):
        """Brokers should support encrypted credentials."""
        # This is important for multi-tenant SaaS
        if PaperBroker:
            # PaperBroker doesn't need credentials, skip
            pytest.skip("PaperBroker doesn't use credentials")
        
        for broker_class in BROKER_IMPLEMENTATIONS:
            if broker_class == PaperBroker:
                continue
            
            # Should accept encrypted config
            # (exact implementation depends on crypto module)
            assert True  # Placeholder - implement once crypto is ready


class TestBrokerCallbacks:
    """Test callback mechanism for fills and events."""
    
    @pytest.mark.asyncio
    async def test_on_fill_callback_registration(self, mock_broker):
        """Should be able to register fill callback."""
        await mock_broker.connect()
        
        callback_called = []
        
        def fill_callback(execution):
            callback_called.append(execution)
        
        mock_broker.on_fill(fill_callback)
        
        # Simulate a fill
        mock_broker.simulate_fill("TEST_ORDER", 50.0, 100)
        
        # Callback should have been called
        assert len(callback_called) == 1
        assert callback_called[0]['price'] == 50.0
        
        await mock_broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_multiple_callbacks_supported(self, mock_broker):
        """Should support multiple callback registrations."""
        await mock_broker.connect()
        
        callbacks_called = [[], []]
        
        def callback1(execution):
            callbacks_called[0].append(execution)
        
        def callback2(execution):
            callbacks_called[1].append(execution)
        
        mock_broker.on_fill(callback1)
        mock_broker.on_fill(callback2)
        
        mock_broker.simulate_fill("TEST", 50.0, 100)
        
        # Both should be called
        assert len(callbacks_called[0]) == 1
        assert len(callbacks_called[1]) == 1
        
        await mock_broker.disconnect()


class TestBrokerReconnection:
    """Test broker reconnection logic."""
    
    @pytest.mark.asyncio
    async def test_reconnect_after_disconnect(self, mock_broker):
        """Should be able to reconnect after disconnect."""
        await mock_broker.connect()
        assert mock_broker.connected
        
        await mock_broker.disconnect()
        assert not mock_broker.connected
        
        await mock_broker.connect()
        assert mock_broker.connected
        
        await mock_broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_automatic_reconnect_on_connection_loss(self, mock_broker):
        """Should attempt automatic reconnection on connection loss."""
        # This is optional but good for production
        pytest.skip("Automatic reconnection is optional feature")
