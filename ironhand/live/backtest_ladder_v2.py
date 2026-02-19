import pandas as pd
import numpy as np
import yfinance as yf
import cipher_b
import json
import os
from datetime import datetime, timedelta

# Configuration
INITIAL_CAPITAL = 100000.0
CAMPAIGN_CAP_PCT = 0.40  # 40% NLV cap per campaign
RUNG_SIZES = [1.0] * 5 + [1.5] * 5 + [2.0] * 5  # 15 rungs

# INSTRUMENTS CONFIG (Updated per Spec v3.2 - No VNQ, added leveraged flag)
INSTRUMENTS_CONFIG = {
    'QQQ': {'signal_source': 'QQQ', 'leveraged': False},
    'SMH': {'signal_source': 'SMH', 'leveraged': False},
    'XLK': {'signal_source': 'XLK', 'leveraged': False},
    'IGV': {'signal_source': 'IGV', 'leveraged': False},
    'IBIT': {'signal_source': 'BTC-USD', 'leveraged': False}, 
    'GLD': {'signal_source': 'GLD', 'leveraged': False},
    'XLE': {'signal_source': 'XLE', 'leveraged': False},
    'XBI': {'signal_source': 'XBI', 'leveraged': False},
    'TQQQ': {'signal_source': 'QQQ', 'leveraged': True},
    'SOXL': {'signal_source': 'SOXL', 'leveraged': True},
    'BITX': {'signal_source': 'BTC-USD', 'leveraged': True},
    'SLV': {'signal_source': 'SLV', 'leveraged': False},
}

START_DATE = "2020-01-01"
END_DATE = "2025-12-31"

class Campaign:
    def __init__(self, ticker, start_date, capital_allocated, atr, anchor_price, regime='AGG'):
        self.ticker = ticker
        self.start_date = start_date
        self.status = 'ACTIVE_' + regime
        self.capital_allocated = capital_allocated
        self.atr = atr
        self.anchor_price = anchor_price
        self.regime = regime
        
        self.rungs = []
        self.positions = 0
        self.avg_price = 0.0
        self.realized_pl = 0.0
        self.last_exit_type = None 
        self.relay_count = 0
        
        self._generate_rungs()

    def _generate_rungs(self):
        spacing_mult = 1.0 if self.regime == 'AGG' else 2.0
        spacing = self.atr * spacing_mult
        
        for i in range(15):
            rung_price = self.anchor_price - ((i + 1) * spacing)
            if rung_price <= 0: break
            
            size_mult = RUNG_SIZES[i]
            share_unit = max(1, int(self.capital_allocated / (self.anchor_price * 22.5)))
            qty = int(share_unit * size_mult)
            
            self.rungs.append({
                'id': i,
                'entry_price': rung_price,
                'qty': qty, 
                'status': 'PENDING',
                'shares': 0,
                'tp_price': rung_price + (self.atr * 1.0)
            })

    def check_fills(self, daily_low, daily_high, date, debug=False):
        # Entries
        for rung in self.rungs:
            if rung['status'] == 'PENDING':
                if daily_low <= rung['entry_price']:
                    rung['status'] = 'FILLED'
                    rung['shares'] = rung['qty']
                    cost = rung['shares'] * rung['entry_price']
                    
                    current_val = self.avg_price * self.positions
                    self.positions += rung['shares']
                    self.avg_price = (current_val + cost) / self.positions
                    
                    if debug: print(f"  [{date}] FILL Rung {rung['id']} @ {rung['entry_price']:.2f} ({rung['shares']} sh)")

        # Exits (Individual TP)
        for rung in self.rungs:
            if rung['status'] == 'FILLED':
                if daily_high >= rung['tp_price']:
                    rung['status'] = 'EXITED'
                    revenue = rung['shares'] * rung['tp_price']
                    cost = rung['shares'] * rung['entry_price']
                    profit = revenue - cost
                    self.realized_pl += profit
                    self.positions -= rung['shares']
                    self.last_exit_type = 'TAKE_PROFIT'
                    if debug: print(f"  [{date}] TP EXIT Rung {rung['id']} @ {rung['tp_price']:.2f} P&L: {profit:.2f}")

    def close_all(self, price, reason):
        if self.positions > 0:
            revenue = self.positions * price
            cost = self.positions * self.avg_price
            profit = revenue - cost
            self.realized_pl += profit
            self.positions = 0
            self.status = reason
            self.last_exit_type = 'MANAGED' if reason == 'EXIT_MANAGED' else 'PROFIT'

    def current_equity(self, current_price):
        if self.positions == 0: return self.realized_pl
        market_val = self.positions * current_price
        cost_basis = self.positions * self.avg_price
        unrealized = market_val - cost_basis
        return self.realized_pl + unrealized
    
    def to_dict(self):
        return {
            'ticker': self.ticker,
            'start_date': str(self.start_date),
            'status': self.status,
            'realized_pl': self.realized_pl,
            'relay_count': self.relay_count,
            'last_exit_type': self.last_exit_type
        }

class BacktestEngine:
    def __init__(self, debug=False, signal_timeframe='weekly'):
        self.config = INSTRUMENTS_CONFIG
        self.data = {}
        self.results = {}
        self.debug = debug
        self.signal_timeframe = signal_timeframe

    def load_data(self):
        print(f"Loading data (Timeframe: {self.signal_timeframe})...")
        
        for ticker, cfg in self.config.items():
            signal_ticker = cfg['signal_source']
            print(f"  Processing {ticker} (Signal Source: {signal_ticker})...\")
            
            try:
                # 1. Fetch Price Data (Daily) for the TRADE ticker
                d_df = yf.download(ticker, start=START_DATE, end=END_DATE, interval="1d", progress=False)
                if isinstance(d_df.columns, pd.MultiIndex): d_df.columns = d_df.columns.get_level_values(0)
                d_df.columns = d_df.columns.str.lower()
                
                if d_df.empty:
                    print(f"    Warning: No price data for {ticker}")
                    continue

                # 2. Fetch Signal Data (Source Ticker)
                if signal_ticker != ticker:
                    sig_df_raw = yf.download(signal_ticker, start="2019-01-01", end=END_DATE, interval=self.signal_timeframe, progress=False)
                    if isinstance(sig_df_raw.columns, pd.MultiIndex): sig_df_raw.columns = sig_df_raw.columns.get_level_values(0)
                    sig_df_raw.columns = sig_df_raw.columns.str.lower()
                else:
                    sig_df_raw = d_df.copy()
                    if self.signal_timeframe != 'daily':
                        sig_df_raw = sig_df_raw.resample(self.signal_timeframe).last()

                if sig_df_raw.empty:
                    print(f"    Warning: No signal data for {signal_ticker}")
                    continue
                
                # 3. Generate Signals
                sig_df = cipher_b.generate_signals(sig_df_raw)
                
                # 4. Merge Signals onto Daily Price Data
                if self.signal_timeframe != 'daily':
                    sig_resampled = sig_df.resample('D').ffill()
                    merged_df = d_df.join(sig_resampled[['green_dot', 'red_dot', 'money_flow', 'mf_velocity', 'atr', 'above_200sma']], how='left')
                    merged_df = merged_df.ffill().dropna()
                else:
                    merged_df = d_df.join(sig_df[['green_dot', 'red_dot', 'money_flow', 'mf_velocity', 'atr', 'above_200sma']], how='left')
                    merged_df = merged_df.ffill().dropna()

                self.data[ticker] = merged_df
                print(f"    Loaded {ticker}: {len(self.data[ticker])} days")
                if 'green_dot' in merged_df.columns:
                     print(f"    Last Green Dot: {merged_df['green_dot'].tail(5)}")

            except Exception as e:
                print(f"    Error processing {ticker}: {e}")

    def run(self):
        final_results = {}
        
        for ticker, df in self.data.items():
            print(f"Simulating {ticker}...")
            capital = INITIAL_CAPITAL
            campaign = None
            campaign_history = []
            
            total_relay_cycles = 0
            
            for date, row in df.iterrows():
                # 1. Update Active Campaign
                if campaign and campaign.status.startswith('ACTIVE'):
                    campaign.check_fills(row['low'], row['high'], date, self.debug)
                    
                    # Relay Rule
                    if campaign.positions == 0 and campaign.last_exit_type == 'TAKE_PROFIT':
                        if not row['red_dot']:
                            # Trigger Relay
                            new_anchor = row['open']
                            regime = 'AGG'
                            if row['money_flow'] > 0 and row['mf_velocity'] < 0: regime = 'DEF'
                            if row['money_flow'] < 0: regime = 'DEF'
                            
                            campaign.anchor_price = new_anchor
                            campaign.atr = row['atr']
                            campaign.regime = regime
                            campaign.rungs = []
                            campaign._generate_rungs()
                            campaign.relay_count += 1
                            total_relay_cycles += 1
                            if self.debug: print(f"  [{date}] RELAY -> {new_anchor:.2f} ({regime})")
                        else:
                            campaign.close_all(row['close'], 'EXIT_PROFIT_RED_DOT')
                            campaign_history.append(campaign)
                            campaign = None
                            if self.debug: print(f"  [{date}] Relay Blocked by Red Dot.")

                # 2. Check Exits (Red Dot)
                if campaign and campaign.status.startswith('ACTIVE') and row['red_dot']:
                    eq = campaign.current_equity(row['close'])
                    if eq > 0:
                        campaign.close_all(row['close'], 'EXIT_PROFIT')
                        campaign_history.append(campaign)
                        campaign = None
                        if self.debug: print(f"  [{date}] RED DOT EXIT (Profit). P&L: {eq:.2f}")
                    else:
                        campaign.status = 'EXIT_MANAGED'
                        if self.debug: print(f"  [{date}] RED DOT EXIT (Managed). Holding.")

                # 3. Managed Exit Handling
                if campaign and campaign.status == 'EXIT_MANAGED':
                    if row['high'] >= campaign.avg_price:
                        campaign.close_all(campaign.avg_price, 'EXIT_MANAGED_DONE')
                        campaign_history.append(campaign)
                        campaign = None
                        if self.debug: print(f"  [{date}] MANAGED EXIT COMPLETE.")

                # 4. Launch New Campaign
                if not campaign:
                    if row['green_dot'] and row['above_200sma']:
                        regime = 'AGG' if row['money_flow'] > 0 else 'DEF'
                        alloc = capital * CAMPAIGN_CAP_PCT
                        campaign = Campaign(ticker, date, alloc, row['atr'], row['close'], regime)
                        if self.debug: print(f"[{date}] NEW CAMPAIGN. Anchor: {row['close']:.2f} ({regime})")

            # Closeout end of sim
            if campaign:
                campaign.close_all(df.iloc[-1]['close'], 'END_SIM')
                campaign_history.append(campaign)

            # Metrics
            total_pl = sum([c.realized_pl for c in campaign_history])
            profitable = len([c for c in campaign_history if c.realized_pl > 0])
            managed = len([c for c in campaign_history if c.status.startswith('EXIT_MANAGED')])
            
            final_results[ticker] = {
                'ticker': ticker,
                'signal_source': self.config[ticker]['signal_source'],
                'leveraged': self.config[ticker]['leveraged'],
                'total_campaigns': len(campaign_history),
                'profitable_exits': profitable,
                'managed_exits': managed,
                'total_pl': total_pl,
                'total_relay_cycles': total_relay_cycles,
                'campaigns': [c.to_dict() for c in campaign_history]
            }
            
        return final_results

if __name__ == "__main__":
    print("Running Backtest with Signal Source Logic (Spec v3.2)...")
    
    # Run Weekly Signals
    print("\n=== WEEKLY SIGNALS ===")
    engine = BacktestEngine(debug=False, signal_timeframe='weekly')
    engine.load_data()
    res = engine.run()
    
    # Save
    with open('backtest_v2_results.json', 'w') as f:
        json.dump(res, f, indent=4, default=str)
        
    print("\nDone.")
