import time
import logging
import json
import math
import os
import argparse
import pandas as pd
from datetime import datetime
from adapter_alpaca import AlpacaClient
from strategy_logic import CoreStrategyLogic
import indicator_engine

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("IronHand")

class IronHandBot:
    def __init__(self, user_id):
        self.user_id = user_id
        self.state_file = f"user_{user_id}_bot_state.json"
        
        # Initialize Client with User ID
        try:
            self.client = AlpacaClient(user_id=self.user_id)
            logger.info(f"Initialized AlpacaClient for User {self.user_id}")
        except Exception as e:
            logger.critical(f"Failed to initialize client: {e}")
            raise

        # --- STRATEGY CONFIG ---
        self.symbol = "TQQQ"
        self.budget = 3000.0
        self.max_total_slots = 5
        self.take_profit_pct = 0.05
        self.core_lock_ratio = 0.75
        self.weekly_rsi_exit_threshold = 70.0
        
        # Default Params (Neutral)
        self.strategy_params = {
            'start_atr': 0.2,
            'end_atr': 2.5,
            'distribution_curve': 1.2,
            'min_trade_value_usd': 100.0,
            'size_increase_factor': 1.0
        }
        # Regime Configs
        self.regimes = {
            'AGGRESSIVE': {'start_atr': 0.15, 'end_atr': 2.0, 'distribution_curve': 1.0},
            'NEUTRAL':    {'start_atr': 0.2,  'end_atr': 2.5, 'distribution_curve': 1.2},
            'DEFENSIVE':  {'start_atr': 0.3,  'end_atr': 3.0, 'distribution_curve': 1.5}
        }
        self.current_regime = 'NEUTRAL'
        self.logic = CoreStrategyLogic(self.strategy_params)
        
    def run(self):
        logger.info(f"--- IronHand SaaS Engine Started ({self.symbol}) for User {self.user_id} ---")
        while True:
            try:
                # Sleep Window: 8 PM to 4 AM EST (20:00 - 04:00)
                now = datetime.now()
                if now.hour >= 20 or now.hour < 4:
                    logger.info("😴 Sleeping for Extended Hours (20:00 - 04:00)...")
                    time.sleep(300) 
                    continue

                self.cycle()
                time.sleep(60) 
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Cycle Error: {e}")
                time.sleep(10)

    def cycle(self):
        # 1. Fetch Price
        price = self.client.get_real_time_price(self.symbol)
        if not price: return
        price = float(price)

        # 2. Check Signals (Euphoria & Regime)
        self.check_signals()

        # 3. Manage Position & Core Lock
        self.manage_core_position(price)

        # 4. Manage Dip Ladder (Buy Side)
        self.manage_dip_ladder(price)

    def check_signals(self):
        """
        Checks for Euphoria (Weekly RSI) and Regime Changes (Daily RSI).
        """
        try:
            # --- EUPHORIA PROTOCOL (Weekly) ---
            weekly_bars = self.client.get_historical_bars(self.symbol, timeframe="1Week", limit=52)
            if weekly_bars and len(weekly_bars) > 20:
                df_w = pd.DataFrame(weekly_bars)
                for col in ['o', 'h', 'l', 'c', 'v']: df_w[col] = df_w[col].astype(float)
                df_w = df_w.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
                
                rsi_series = indicator_engine._calculate_rsi_series(df_w['close'], period=14)
                current_weekly_rsi = rsi_series.iloc[-1]
                
                if current_weekly_rsi > self.weekly_rsi_exit_threshold:
                    logger.critical(f"🚨 EUPHORIA PROTOCOL TRIGGERED: Weekly RSI {current_weekly_rsi:.2f} > {self.weekly_rsi_exit_threshold}")
                    self.execute_euphoria_liquidation()
                    return # Stop cycle after liquidation

            # --- REGIME HYSTERESIS (Daily) ---
            daily_bars = self.client.get_historical_bars(self.symbol, timeframe="1Day", limit=100)
            if daily_bars and len(daily_bars) > 20:
                df_d = pd.DataFrame(daily_bars)
                for col in ['o', 'h', 'l', 'c', 'v']: df_d[col] = df_d[col].astype(float)
                df_d = df_d.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
                
                rsi_series = indicator_engine._calculate_rsi_series(df_d['close'], period=14)
                daily_rsi = rsi_series.iloc[-1]
                
                new_regime = self.current_regime
                if daily_rsi < 30: new_regime = 'AGGRESSIVE'
                elif daily_rsi > 70: new_regime = 'DEFENSIVE'
                elif 40 <= daily_rsi <= 60: new_regime = 'NEUTRAL'
                
                if new_regime != self.current_regime:
                    logger.info(f"🔄 REGIME CHANGE: {self.current_regime} -> {new_regime} (Daily RSI: {daily_rsi:.2f})")
                    self.current_regime = new_regime
                    self.strategy_params.update(self.regimes[new_regime])
                    self.logic = CoreStrategyLogic(self.strategy_params)
                    
        except Exception as e:
            logger.error(f"Signal Check Error: {e}")

    def execute_euphoria_liquidation(self):
        """Liquidates ALL positions and cancels ALL orders."""
        logger.warning("EXECUTING EUPHORIA LIQUIDATION...")
        self.client.cancel_all_orders()
        time.sleep(2)
        pos = self.client.get_position(self.symbol)
        qty = float(pos['qty']) if pos else 0.0
        
        if qty > 0:
            logger.warning(f"Selling {qty} shares at MARKET.")
            self.client.place_order(self.symbol, qty, 'sell', 'market', time_in_force='day')
        else:
            logger.info("No position to liquidate.")

    def manage_core_position(self, current_price):
        """
        Manages exits:
        1. Implements 75/25 Split for new shares
        2. Places GTC Limit Sell (Take Profit)
        """
        pos = self.client.get_position(self.symbol)
        if not pos: return

        qty_held = float(pos['qty'])
        if qty_held <= 0: return
        
        # --- CORE PROFIT LOCK (75/25) ---
        open_sells = self.client.get_open_orders(self.symbol, side='sell')
        locked_in_sells = sum([float(o['qty']) for o in open_sells])
        
        unlocked_shares = qty_held - locked_in_sells
        
        if unlocked_shares > 1.0: 
            logger.info(f"Core Logic: Found {unlocked_shares} unlocked shares. Locking profit...")
            shares_to_sell = math.floor(unlocked_shares * self.core_lock_ratio)
            
            if shares_to_sell > 0:
                target_price = current_price * (1 + self.take_profit_pct)
                logger.info(f"  > Placing GTC Sell Limit for {shares_to_sell} shares @ ${target_price:.2f}")
                self.client.place_order(
                    symbol=self.symbol,
                    qty=shares_to_sell,
                    side='sell',
                    type='limit',
                    limit_price=target_price,
                    time_in_force='gtc' # SELLS ARE ALWAYS GTC
                )

    def reconcile_orders(self, existing_orders, target_orders):
        """
        Optimized diffing to avoid cancel/replace churn.
        """
        to_keep = [] 
        to_cancel = [] 
        to_place = [] 
        
        remaining_targets = target_orders.copy()
        
        for order in existing_orders:
            try:
                if 'limit_price' not in order or not order['limit_price']:
                    to_cancel.append(order['id'])
                    continue
                    
                price = float(order['limit_price'])
                
                match_idx = -1
                for i, target in enumerate(remaining_targets):
                    if abs(price - target['price']) < 0.02:
                        match_idx = i
                        break
                
                if match_idx >= 0:
                    to_keep.append(order['id'])
                    del remaining_targets[match_idx]
                else:
                    to_cancel.append(order['id'])
            except Exception as e:
                logger.error(f"Reconciliation error on order {order}: {e}")
                
        to_place = remaining_targets
        return to_cancel, to_place

    def manage_dip_ladder(self, current_price):
        """
        Regenerates the Buy Ladder based on current price.
        """
        open_buys = self.client.get_open_orders(self.symbol, side='buy')

        pos = self.client.get_position(self.symbol)
        qty_held = float(pos['qty']) if pos else 0.0
        current_value = qty_held * current_price
        
        cost_per_slot = self.budget / self.max_total_slots
        filled_slots = int(current_value / cost_per_slot)
        slots_available = self.max_total_slots - filled_slots
        
        if slots_available <= 0:
            if open_buys:
                logger.info("Max slots filled. Cancelling all buys.")
                for o in open_buys: self.client.cancel_order(o['id'])
            return

        atr = current_price * 0.02 
        remaining_budget = self.budget - current_value
        if remaining_budget < 100: return

        target_orders = self.logic.generate_ladder_orders(
            current_price=current_price,
            atr=atr,
            max_slots=slots_available,
            cash_to_deploy=remaining_budget
        )
        
        if not target_orders: return
        
        to_cancel, to_place = self.reconcile_orders(open_buys, target_orders)
        
        if to_cancel:
            logger.info(f"Reconciliation: Cancelling {len(to_cancel)} zombie/old orders...")
            for oid in to_cancel:
                self.client.cancel_order(oid)
            if to_place: time.sleep(1) 
            
        if to_place:
            logger.info(f"Reconciliation: Placing {len(to_place)} new orders...")
            for o in to_place:
                self.client.place_order(
                    symbol=self.symbol, 
                    qty=o['quantity'], 
                    side='buy',
                    type='limit',
                    limit_price=o['price'],
                    time_in_force='day' # BUYS ARE DAY (GTD)
                )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='IronHand SaaS Bot')
    parser.add_argument('--user_id', type=str, required=True, help='User ID for multi-tenant config')
    args = parser.parse_args()
    
    bot = IronHandBot(user_id=args.user_id)
    bot.run()
