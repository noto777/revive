import pandas as pd
import numpy as np
import yfinance as yf
import cipher_b
from datetime import datetime, timedelta
import os

# CONFIG
SYMBOL = 'QQQ'
DATA_FILE = '/root/.openclaw/workspace-personal/ironhand/live/data/QQQ_1min.csv'
INITIAL_CAPITAL = 100000.0
RUNG_SIZES = [1.0] * 5 + [1.5] * 5 + [2.0] * 5  # 15 rungs

class DataManager:
    def __init__(self, symbol, csv_path):
        self.symbol = symbol
        self.csv_path = csv_path
        self.intraday_df = None
        self.daily_signals = None
        self.weekly_signals = None

    def load_and_prep(self):
        print(f"Loading 1-minute data from {self.csv_path}...")
        df = pd.read_csv(self.csv_path, parse_dates=['Date'])
        df.rename(columns={'Date': 'timestamp', 'Open':'open', 'High':'high', 'Low':'low', 'Close':'close', 'Volume':'volume'}, inplace=True)
        df.set_index('timestamp', inplace=True)
        self.intraday_df = df.sort_index()
        
        print(f"  Intraday Range: {self.intraday_df.index.min()} to {self.intraday_df.index.max()}")

        print("Fetching historical context from Yahoo...")
        history_start = (self.intraday_df.index.min() - timedelta(days=700)).strftime('%Y-%m-%d')
        
        daily_df = yf.download(self.symbol, start=history_start, end=None, progress=False)
        if isinstance(daily_df.columns, pd.MultiIndex): daily_df.columns = daily_df.columns.get_level_values(0)
        daily_df.columns = daily_df.columns.str.lower()
        
        print("Generating Signals...")
        self.daily_signals = cipher_b.generate_signals(daily_df)
        print("Data Prep Complete.")

class LadderEngine:
    def __init__(self, data_manager):
        self.dm = data_manager
        self.capital = INITIAL_CAPITAL
        self.campaign = None
        self.campaign_log = []
        self.active_orders = [] # List of Rung objects

    def generate_ladder(self, anchor_price, atr, mode='LINEAR'):
        rungs = []
        # AGGRESSIVE SIZING: Assume max depth is Rung 7 (7 units approx) instead of 22.5
        # This 3x's the position size.
        base_shares = max(1, int((self.capital * 0.40) / (anchor_price * 7.0)))
        
        current_price = anchor_price
        
        for i in range(14): # Rungs 2-15
            # Determine Spacing
            if mode == 'LINEAR':
                spacing = atr * 1.0
            elif mode == 'PROGRESSIVE':
                # 0.2, 0.4, 0.6, 0.8, 1.0 (capped at 1.0 or continue?)
                # Logic: Spacing[i] = 0.2 * (i+1)
                # i=0 (Rung 2) -> 0.2 ATR gap
                # i=1 (Rung 3) -> 0.4 ATR gap
                # ...
                spacing_mult = 0.2 * (i + 1)
                if spacing_mult > 1.0: spacing_mult = 1.0 # Cap at 1.0 ATR
                spacing = atr * spacing_mult
            
            # Linear adds from Anchor.
            # Progressive adds from Previous Rung?
            # Standard "ladder spacing" usually refers to distance between rungs.
            
            price = current_price - spacing
            current_price = price
            
            real_rung_number = i + 2
            
            if real_rung_number <= 5: multiplier = 1.0
            elif real_rung_number <= 10: multiplier = 1.5
            else: multiplier = 2.0
            
            qty = int(base_shares * multiplier)
            
            rungs.append({
                'id': real_rung_number,
                'limit_price': price,
                'qty': qty,
                'status': 'PENDING',
                'tp_price': price + (atr * 1.0)
            })
        return rungs, base_shares

    def run(self):
        print("\n--- Starting COMPARAISON: LINEAR vs PROGRESSIVE (2020-2022) ---")
        
        modes = ['LINEAR', 'PROGRESSIVE']
        
        for mode in modes:
            print(f"\n>>> Running Mode: {mode} <<<")
            self.campaign = None
            self.campaign_log = []
            
            # Reset Data iterator logic inside loop or re-group
            df = self.dm.intraday_df
            days = df.groupby(df.index.date)
            
            for date, day_data in days:
                try:
                    idx_loc = self.dm.daily_signals.index.get_indexer([date], method='pad')[0]
                    daily_row = self.dm.daily_signals.iloc[idx_loc]
                except: continue
                
                green_dot = daily_row['green_dot']
                red_dot = daily_row['red_dot']
                atr = daily_row['atr']
                
                market_open = day_data.between_time('09:30', '16:00')
                if market_open.empty: continue
                
                # 1. Start New Campaign
                if self.campaign is None and green_dot:
                    anchor_price = market_open.iloc[0]['open']
                    limit_rungs, base_shares = self.generate_ladder(anchor_price, atr, mode)
                    
                    self.campaign = {
                        'start_date': date,
                        'anchor': anchor_price,
                        'rungs': limit_rungs,
                        'positions': [],
                        'realized_pnl': 0.0
                    }
                    
                    # Market Buy Rung 1
                    rung1_qty = int(base_shares * 1.0)
                    entry_time = market_open.index[0]
                    self.campaign['positions'].append({
                        'id': 1,
                        'entry_price': anchor_price,
                        'qty': rung1_qty,
                        'tp_price': anchor_price + (atr * 1.0),
                        'fill_time': entry_time
                    })
                    # print(f"[{date}] New Campaign ({mode})")

                # 2. Manage Active
                if self.campaign:
                    if red_dot and len(self.campaign['positions']) > 0:
                        exit_price = market_open.iloc[0]['open']
                        pnl = sum((exit_price - p['entry_price']) * p['qty'] for p in self.campaign['positions'])
                        self.campaign['realized_pnl'] += pnl
                        # print(f"  RED DOT EXIT: {pnl:.2f}")
                        self.campaign_log.append(self.campaign)
                        self.campaign = None
                        continue

                    for ts, bar in market_open.iterrows():
                        low, high = bar['low'], bar['high']
                        
                        # Fills
                        for rung in self.campaign['rungs']:
                            if rung['status'] == 'PENDING' and low <= rung['limit_price']:
                                rung['status'] = 'FILLED'
                                rung['entry_price'] = rung['limit_price']
                                self.campaign['positions'].append(rung)
                                # print(f"  Filled Rung {rung['id']}")
                        
                        # Exits
                        for pos in self.campaign['positions'][:]:
                            if high >= pos['tp_price']:
                                pnl = (pos['tp_price'] - pos['entry_price']) * pos['qty']
                                self.campaign['realized_pnl'] += pnl
                                self.campaign['positions'].remove(pos)
                                if len(self.campaign['positions']) == 0:
                                    self.campaign_log.append(self.campaign)
                                    self.campaign = None
                                    break
                        if self.campaign is None: break

            total_pnl = sum(c['realized_pnl'] for c in self.campaign_log)
            print(f"Total P&L ({mode}): ${total_pnl:.2f}")
            print(f"Campaigns: {len(self.campaign_log)}")

if __name__ == "__main__":
    dm = DataManager(SYMBOL, DATA_FILE)
    dm.load_and_prep()
    
    eng = LadderEngine(dm)
    eng.run()
