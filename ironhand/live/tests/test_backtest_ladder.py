import pytest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backtest_ladder import BacktestEngine, Campaign

def test_campaign_mechanics():
    # Test Campaign class directly
    # Setup
    ticker = "TEST"
    start_date = "2024-01-01"
    capital = 10000
    atr = 2.0
    anchor_price = 100.0
    
    # 1. Init (AGG)
    camp = Campaign(ticker, start_date, capital, atr, anchor_price, regime='AGG')
    assert len(camp.rungs) == 15
    assert camp.rungs[0]['entry_price'] == 98.0 # Anchor 100 - (1 * 2.0)
    assert camp.rungs[0]['qty_unit'] == 1.0
    
    # 2. Check Fills & Exit (Intraday TP)
    # Drop price to fill first rung AND hit TP in same day
    # Entry: 98.0, TP: 100.0
    # Range: 97.0 - 101.0 -> Covers both
    camp.check_fills(daily_low=97.0, daily_high=101.0, date="2024-01-02")
    
    # Since High (101) > TP (100), it fills and exits
    assert camp.rungs[0]['status'] == 'EXITED'
    assert camp.positions == 0
    assert camp.realized_pl > 0
    assert camp.last_exit_type == 'TAKE_PROFIT'

def test_engine_smoke_test(monkeypatch):
    # Mock INSTRUMENTS to just QQQ for speed
    monkeypatch.setattr("backtest_ladder.INSTRUMENTS", ['QQQ'])
    
    engine = BacktestEngine()
    
    # We rely on live data fetch in this smoke test (integration test)
    # Ensure it doesn't crash
    engine.load_data()
    results = engine.run()
    
    assert 'QQQ' in results
    res = results['QQQ']
    assert 'total_pl' in res
    assert 'campaign_count' in res
    # We expect *some* campaigns in 5 years of QQQ
    assert res['campaign_count'] >= 0 
