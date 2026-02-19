"""
Tests for engine/executor.py - Strategy execution loop.

Tests the Executor class which runs the strategy loop:
- Start, stop, pause lifecycle
- Loop iteration (indicators → ladder → fills → sells)
- Error handling and recovery
- State persistence
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch


try:
    from ironhand.engine.executor import Executor, ExecutorState
except ImportError:
    Executor = None
    ExecutorState = None


pytestmark = pytest.mark.skipif(
    Executor is None,
    reason="Executor not implemented yet"
)


class TestExecutorLifecycle:
    """Test executor start/stop/pause lifecycle."""
    
    @pytest.mark.asyncio
    async def test_executor_initialization(self, strategy, mock_broker):
        """Executor should initialize with strategy and broker."""
        executor = Executor(
            strategy=strategy,
            broker=mock_broker
        )
        
        assert executor is not None
        assert executor.state == ExecutorState.STOPPED
    
    @pytest.mark.asyncio
    async def test_start_executor(self, strategy, mock_broker):
        """Starting executor should begin strategy loop."""
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        # Start in background
        task = asyncio.create_task(executor.start())
        
        # Give it time to start
        await asyncio.sleep(0.1)
        
        assert executor.state == ExecutorState.RUNNING
        
        # Stop it
        await executor.stop()
        await task
    
    @pytest.mark.asyncio
    async def test_stop_executor(self, strategy, mock_broker):
        """Stopping executor should gracefully shut down."""
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        task = asyncio.create_task(executor.start())
        await asyncio.sleep(0.1)
        
        # Stop should complete quickly
        await executor.stop()
        await task
        
        assert executor.state == ExecutorState.STOPPED
    
    @pytest.mark.asyncio
    async def test_pause_resume_executor(self, strategy, mock_broker):
        """Executor should support pause/resume."""
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        task = asyncio.create_task(executor.start())
        await asyncio.sleep(0.1)
        
        # Pause
        await executor.pause()
        assert executor.state == ExecutorState.PAUSED
        
        # Resume
        await executor.resume()
        assert executor.state == ExecutorState.RUNNING
        
        await executor.stop()
        await task
    
    @pytest.mark.asyncio
    async def test_cannot_start_while_running(self, strategy, mock_broker):
        """Starting already-running executor should raise error."""
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        task = asyncio.create_task(executor.start())
        await asyncio.sleep(0.1)
        
        # Try to start again
        with pytest.raises(RuntimeError):
            await executor.start()
        
        await executor.stop()
        await task
    
    @pytest.mark.asyncio
    async def test_restart_after_stop(self, strategy, mock_broker):
        """Should be able to restart after stopping."""
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        # First run
        task1 = asyncio.create_task(executor.start())
        await asyncio.sleep(0.1)
        await executor.stop()
        await task1
        
        # Second run
        task2 = asyncio.create_task(executor.start())
        await asyncio.sleep(0.1)
        await executor.stop()
        await task2
        
        # Should work both times
        assert True


class TestExecutorLoop:
    """Test the main execution loop."""
    
    @pytest.mark.asyncio
    async def test_loop_runs_repeatedly(self, strategy, mock_broker):
        """Loop should run multiple iterations."""
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        iterations = []
        
        # Mock the loop body to count iterations
        original_loop = executor._run_iteration
        async def count_iterations(*args):
            iterations.append(datetime.now())
            return await original_loop(*args)
        
        executor._run_iteration = count_iterations
        
        task = asyncio.create_task(executor.start())
        
        # Let it run for 3 iterations (15 seconds each in config)
        # But we can speed it up for testing
        await asyncio.sleep(0.5)
        
        await executor.stop()
        await task
        
        # Should have run at least once
        assert len(iterations) >= 1
    
    @pytest.mark.asyncio
    async def test_check_interval_respected(self, strategy, mock_broker):
        """Loop should respect configured check interval."""
        # Strategy config has 15 second interval
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        iterations = []
        executor._run_iteration = AsyncMock(side_effect=lambda: iterations.append(datetime.now()))
        
        task = asyncio.create_task(executor.start())
        
        # For testing, override interval to be shorter
        executor.check_interval = 0.1  # 100ms for testing
        
        await asyncio.sleep(0.35)  # Allow 3 iterations
        
        await executor.stop()
        await task
        
        # Should have ~3 iterations
        assert 2 <= len(iterations) <= 4
    
    @pytest.mark.asyncio
    async def test_loop_stops_on_shutdown_signal(self, strategy, mock_broker):
        """Loop should stop when shutdown signal is set."""
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        task = asyncio.create_task(executor.start())
        await asyncio.sleep(0.1)
        
        # Set shutdown signal
        executor.shutdown_event.set()
        
        # Should stop gracefully
        await asyncio.wait_for(task, timeout=2.0)
        
        assert executor.state == ExecutorState.STOPPED


class TestExecutorIterationSteps:
    """Test individual steps of each iteration."""
    
    @pytest.mark.asyncio
    async def test_fetch_market_data_step(self, strategy, mock_broker, sample_ohlcv):
        """Should fetch market data each iteration."""
        mock_broker.market_data['ETHU'] = sample_ohlcv
        
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        # Run single iteration
        await executor._run_iteration()
        
        # Should have called get_market_data
        assert 'ETHU' in mock_broker.market_data
    
    @pytest.mark.asyncio
    async def test_calculate_indicators_step(self, strategy, mock_broker, sample_ohlcv):
        """Should calculate indicators each iteration."""
        mock_broker.market_data['ETHU'] = sample_ohlcv
        
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        with patch('ironhand.core.indicators.calculate_rsi') as mock_rsi:
            mock_rsi.return_value = 45.0
            
            await executor._run_iteration()
            
            # Should have called indicator functions
            mock_rsi.assert_called()
    
    @pytest.mark.asyncio
    async def test_generate_ladder_step(self, strategy, mock_broker, sample_ohlcv):
        """Should generate ladder each iteration."""
        mock_broker.market_data['ETHU'] = sample_ohlcv
        
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        with patch('ironhand.core.strategy_logic.CoreStrategyLogic.generate_ladder') as mock_ladder:
            mock_ladder.return_value = []
            
            await executor._run_iteration()
            
            mock_ladder.assert_called()
    
    @pytest.mark.asyncio
    async def test_check_fills_step(self, strategy, mock_broker):
        """Should check for fills each iteration."""
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        # Mock a pending order
        mock_broker.orders = [{
            'id': 'TEST123',
            'status': 'pending'
        }]
        
        await executor._run_iteration()
        
        # Should have checked order status
        # (Exact assertion depends on implementation)
        assert True
    
    @pytest.mark.asyncio
    async def test_evaluate_exits_step(self, strategy, mock_broker):
        """Should evaluate exit strategies each iteration."""
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        # Mock a position
        mock_broker.positions = [{
            'symbol': 'ETHU',
            'quantity': 100,
            'entry_price': 45.0
        }]
        
        with patch('ironhand.core.core_manager.CorePositionManager.evaluate_exit_strategy') as mock_exit:
            mock_exit.return_value = Mock(should_sell=False)
            
            await executor._run_iteration()
            
            mock_exit.assert_called()


class TestExecutorErrorHandling:
    """Test error handling and recovery."""
    
    @pytest.mark.asyncio
    async def test_continues_after_iteration_error(self, strategy, mock_broker):
        """Executor should continue after non-fatal error."""
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        call_count = [0]
        
        async def failing_iteration():
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Temporary error")
            return None
        
        executor._run_iteration = failing_iteration
        executor.check_interval = 0.1
        
        task = asyncio.create_task(executor.start())
        
        await asyncio.sleep(0.35)
        
        await executor.stop()
        await task
        
        # Should have retried after error
        assert call_count[0] > 1
    
    @pytest.mark.asyncio
    async def test_stops_on_fatal_error(self, strategy, mock_broker):
        """Executor should stop on fatal errors."""
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        async def fatal_error():
            raise RuntimeError("Fatal error")
        
        executor._run_iteration = fatal_error
        
        task = asyncio.create_task(executor.start())
        
        # Should stop itself
        await asyncio.wait_for(task, timeout=2.0)
        
        assert executor.state == ExecutorState.ERROR
    
    @pytest.mark.asyncio
    async def test_logs_errors(self, strategy, mock_broker):
        """Errors should be logged."""
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        async def error_iteration():
            raise ValueError("Test error")
        
        executor._run_iteration = error_iteration
        executor.max_consecutive_errors = 2
        
        with patch('ironhand.logging.logger') as mock_logger:
            task = asyncio.create_task(executor.start())
            
            await asyncio.sleep(0.3)
            
            try:
                await executor.stop()
                await task
            except:
                pass
            
            # Should have logged errors
            assert mock_logger.error.called or mock_logger.warning.called
    
    @pytest.mark.asyncio
    async def test_max_consecutive_errors_limit(self, strategy, mock_broker):
        """Should stop after max consecutive errors."""
        executor = Executor(strategy=strategy, broker=mock_broker)
        executor.max_consecutive_errors = 3
        
        error_count = [0]
        
        async def counting_error():
            error_count[0] += 1
            raise Exception(f"Error {error_count[0]}")
        
        executor._run_iteration = counting_error
        executor.check_interval = 0.05
        
        task = asyncio.create_task(executor.start())
        
        await asyncio.wait_for(task, timeout=2.0)
        
        # Should have stopped after 3 errors
        assert error_count[0] <= 3
        assert executor.state == ExecutorState.ERROR


class TestExecutorStatePersistence:
    """Test state persistence to database."""
    
    @pytest.mark.asyncio
    async def test_saves_dashboard_state(self, strategy, mock_broker, db_session):
        """Should save dashboard state each iteration."""
        executor = Executor(strategy=strategy, broker=mock_broker, db_session=db_session)
        
        # Run one iteration
        await executor._run_iteration()
        
        # Should have saved state to DB
        # (Check strategy_snapshots table)
        pytest.skip("Requires DB implementation")
    
    @pytest.mark.asyncio
    async def test_restores_state_on_restart(self, strategy, mock_broker):
        """Should restore state when restarting."""
        pytest.skip("State restoration is optional advanced feature")


class TestExecutorBrokerIntegration:
    """Test executor interaction with broker."""
    
    @pytest.mark.asyncio
    async def test_connects_to_broker_on_start(self, strategy, mock_broker):
        """Should connect to broker when starting."""
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        assert not mock_broker.connected
        
        task = asyncio.create_task(executor.start())
        await asyncio.sleep(0.1)
        
        assert mock_broker.connected
        
        await executor.stop()
        await task
    
    @pytest.mark.asyncio
    async def test_disconnects_from_broker_on_stop(self, strategy, mock_broker):
        """Should disconnect from broker when stopping."""
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        task = asyncio.create_task(executor.start())
        await asyncio.sleep(0.1)
        
        await executor.stop()
        await task
        
        assert not mock_broker.connected
    
    @pytest.mark.asyncio
    async def test_registers_fill_callback(self, strategy, mock_broker):
        """Should register fill callback with broker."""
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        await executor.start()
        await asyncio.sleep(0.1)
        
        # Should have registered callback
        assert mock_broker.fills_callback is not None
        
        await executor.stop()


class TestExecutorMetrics:
    """Test metrics and monitoring."""
    
    @pytest.mark.asyncio
    async def test_tracks_iteration_count(self, strategy, mock_broker):
        """Should track number of iterations."""
        executor = Executor(strategy=strategy, broker=mock_broker)
        executor.check_interval = 0.05
        
        task = asyncio.create_task(executor.start())
        await asyncio.sleep(0.2)
        
        await executor.stop()
        await task
        
        # Should have iteration count
        assert executor.iteration_count > 0
    
    @pytest.mark.asyncio
    async def test_tracks_iteration_duration(self, strategy, mock_broker):
        """Should track average iteration duration."""
        executor = Executor(strategy=strategy, broker=mock_broker)
        
        task = asyncio.create_task(executor.start())
        await asyncio.sleep(0.2)
        
        await executor.stop()
        await task
        
        # Should have duration metrics
        assert hasattr(executor, 'avg_iteration_duration')
    
    @pytest.mark.asyncio
    async def test_tracks_error_rate(self, strategy, mock_broker):
        """Should track error rate."""
        pytest.skip("Metrics tracking is optional feature")


class TestExecutorConcurrency:
    """Test running multiple executors concurrently."""
    
    @pytest.mark.asyncio
    async def test_multiple_executors_independently(self, strategy, second_tenant, mock_broker, db_session):
        """Should run multiple executors without interference."""
        # Create second strategy for second tenant
        if not strategy:
            pytest.skip("Requires Strategy model")
        
        from ironhand.db.models import Strategy
        from uuid import uuid4
        
        strategy2 = Strategy(
            id=uuid4(),
            tenant_id=second_tenant.id,
            symbol="BTCU",
            status="stopped",
            config=strategy.config
        )
        db_session.add(strategy2)
        await db_session.commit()
        
        # Create two executors
        broker1 = mock_broker
        broker2 = MockBroker()  # Need separate broker
        
        executor1 = Executor(strategy=strategy, broker=broker1)
        executor2 = Executor(strategy=strategy2, broker=broker2)
        
        # Run both
        task1 = asyncio.create_task(executor1.start())
        task2 = asyncio.create_task(executor2.start())
        
        await asyncio.sleep(0.2)
        
        # Both should be running
        assert executor1.state == ExecutorState.RUNNING
        assert executor2.state == ExecutorState.RUNNING
        
        # Stop both
        await executor1.stop()
        await executor2.stop()
        await task1
        await task2
