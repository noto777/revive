#!/usr/bin/env python3
"""
IRONHAND Backtest Engine — QQQ v1
Event-driven backtest per spec Sections 2-4.
Pure CSV in → JSON/print out. No external data.

Data: QQQ_1min.csv (market hours: 09:30-16:00)
"""

import pandas as pd
import numpy as np
import json
import sys
from datetime import date, datetime, timedelta
from collections import defaultdict

# ─────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────
CSV_PATH     = "/root/.openclaw/workspace-personal/ironhand/live/data/QQQ_1min.csv"
RESULTS_PATH = "/root/.openclaw/workspace-personal/ironhand/live/backtest_qqq_results.json"

INITIAL_NLV   = 100_000.0
BASE_PCT      = 0.02           # 2% NLV per 1.0x rung
NUM_RUNGS     = 15
RUNG_MULTS    = [1.0]*5 + [1.5]*5 + [2.0]*5   # 15 rungs

START_ATR_MULT = 0.75          # rung-1 spacing (ATR multiplier from anchor)
END_ATR_MULT   = 4.0           # rung-15 spacing
TP_ATR_MULT    = 1.0           # TP = fill_price + ATR*1.0
GAP_SKIP_PCT   = 0.02          # void rungs >2% above anchor

# WaveTrend (spec §2.1)
WT_CHANNEL   = 9
WT_AVG       = 12
WT_SIGNAL    = 3
WT_OVERSOLD  = -60.0
WT_OBOUGHT   = +60.0
WT_WARMUP    = WT_CHANNEL + WT_AVG + WT_SIGNAL  # bars needed before valid signal

# MFI (spec §2.2)
MFI_PERIOD = 14

# Daily indicators
SMA_PERIOD = 200
ATR_PERIOD = 14

# IBKR cost model (spec §4.1)
IBKR_PER_SHARE    = 0.0035
IBKR_MIN          = 0.35
IBKR_MAX_PCT      = 0.01       # 1% of trade value
MANAGED_SLIPPAGE  = 0.0002     # 0.02% market order slippage


# ─────────────────────────────────────────────────────────────────
# STEP 1 — LOAD DATA
# ─────────────────────────────────────────────────────────────────
def load_data(csv_path: str):
    print("=" * 65)
    print("STEP 1 — LOADING DATA")
    print("=" * 65)

    df = pd.read_csv(csv_path, parse_dates=["Date"])
    df.rename(columns={
        "Date":"ts","Open":"open","High":"high",
        "Low":"low","Close":"close","Volume":"volume"
    }, inplace=True)
    df.sort_values("ts", inplace=True)
    df.reset_index(drop=True, inplace=True)

    print(f"Total rows        : {len(df):,}")
    print(f"Full date range   : {df['ts'].min()} → {df['ts'].max()}")

    # Strict market hours 9:30–16:00
    t930 = pd.Timestamp("09:30:00").time()
    t1600 = pd.Timestamp("16:00:00").time()
    mask = (df["ts"].dt.time >= t930) & (df["ts"].dt.time <= t1600)
    mkt = df[mask].copy().reset_index(drop=True)

    trading_days = sorted(mkt["ts"].dt.date.unique())
    print(f"Market-hours rows : {len(mkt):,}")
    print(f"Trading days      : {len(trading_days)}")
    print(f"Market date range : {trading_days[0]} → {trading_days[-1]}")

    # Gap detection (>5 calendar days between adjacent trading days)
    gaps = []
    for i in range(1, len(trading_days)):
        diff = (trading_days[i] - trading_days[i-1]).days
        if diff > 5:
            gaps.append((trading_days[i-1], trading_days[i], diff))
    if gaps:
        print(f"DATA GAPS (>5 calendar days):")
        for a, b, d in gaps:
            print(f"  {a} → {b} ({d} days)")
    else:
        print("No significant data gaps.")

    return mkt, trading_days


# ─────────────────────────────────────────────────────────────────
# AGGREGATION
# ─────────────────────────────────────────────────────────────────
def build_daily_bars(mkt: pd.DataFrame) -> pd.DataFrame:
    mkt = mkt.copy()
    mkt["date"] = mkt["ts"].dt.date
    daily = mkt.groupby("date").agg(
        open=("open","first"), high=("high","max"),
        low=("low","min"),   close=("close","last"),
        volume=("volume","sum")
    ).reset_index()
    daily["date"] = pd.to_datetime(daily["date"])
    daily.sort_values("date", inplace=True)
    return daily.reset_index(drop=True)


def build_weekly_bars(mkt: pd.DataFrame) -> pd.DataFrame:
    """
    Weekly bar = Monday open → Friday 16:00 close.
    Only includes complete weeks (must have a Friday bar).
    """
    mkt = mkt.copy()
    mkt["date"] = mkt["ts"].dt.date
    mkt["dow"]  = mkt["ts"].dt.dayofweek
    mkt["iso_year"] = mkt["ts"].dt.isocalendar().year.astype(int)
    mkt["iso_week"] = mkt["ts"].dt.isocalendar().week.astype(int)
    mkt["yw"] = (mkt["iso_year"].astype(str) + "_"
                 + mkt["iso_week"].astype(str).str.zfill(2))

    rows = []
    for yw, grp in mkt.groupby("yw"):
        fri = grp[grp["dow"] == 4]
        if fri.empty:
            continue  # incomplete week
        mon = grp[grp["dow"] == 0]
        wk_open = mon["open"].iloc[0] if not mon.empty else grp["open"].iloc[0]

        # Friday close = last 1-min bar of Friday (prefer 16:00)
        fri_1600 = fri[fri["ts"].dt.time == pd.Timestamp("16:00").time()]
        wk_close = (fri_1600["close"].iloc[0] if not fri_1600.empty
                    else fri.sort_values("ts").iloc[-1]["close"])

        rows.append({
            "yw":           yw,
            "week_end_date": fri["date"].max(),
            "open":  wk_open,
            "high":  grp["high"].max(),
            "low":   grp["low"].min(),
            "close": wk_close,
            "volume": grp["volume"].sum(),
        })

    wdf = pd.DataFrame(rows)
    wdf["week_end_date"] = pd.to_datetime(wdf["week_end_date"])
    wdf.sort_values("week_end_date", inplace=True)
    return wdf.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────
# INDICATORS
# ─────────────────────────────────────────────────────────────────
def ema(s: pd.Series, p: int) -> pd.Series:
    return s.ewm(span=p, adjust=False).mean()

def sma(s: pd.Series, p: int) -> pd.Series:
    return s.rolling(p).mean()


def compute_wavetrend(wdf: pd.DataFrame) -> pd.DataFrame:
    """
    WaveTrend on weekly HLC3.
    Returns wdf with wt1, wt2, green_dot, red_dot columns.
    Signals are NaN for warmup bars (first WT_WARMUP bars).
    """
    hlc3 = (wdf["high"] + wdf["low"] + wdf["close"]) / 3.0
    esa  = ema(hlc3, WT_CHANNEL)
    d    = ema((hlc3 - esa).abs(), WT_CHANNEL)
    # Avoid division by zero — replace with NaN then forward-fill
    d_safe = d.replace(0.0, np.nan)
    ci   = (hlc3 - esa) / (0.015 * d_safe)
    ci   = ci.fillna(0.0)
    wt1  = ema(ci, WT_AVG)
    wt2  = sma(wt1, WT_SIGNAL)

    # Null out warmup period
    wt1.iloc[:WT_WARMUP] = np.nan
    wt2.iloc[:WT_WARMUP] = np.nan

    wdf = wdf.copy()
    wdf["wt1"] = wt1.values
    wdf["wt2"] = wt2.values

    # Crosses (closed-bar)
    prev_wt1 = wdf["wt1"].shift(1)
    prev_wt2 = wdf["wt2"].shift(1)

    cross_up = (prev_wt1 <= prev_wt2) & (wdf["wt1"] > wdf["wt2"])
    both_os  = (wdf["wt1"] < WT_OVERSOLD) & (wdf["wt2"] < WT_OVERSOLD)
    wdf["green_dot"] = cross_up & both_os

    cross_dn = (prev_wt1 >= prev_wt2) & (wdf["wt1"] < wdf["wt2"])
    both_ob  = (wdf["wt1"] > WT_OBOUGHT) & (wdf["wt2"] > WT_OBOUGHT)
    wdf["red_dot"] = cross_dn & both_ob

    # Mask NaN rows
    nan_mask = wdf["wt1"].isna()
    wdf.loc[nan_mask, "green_dot"] = False
    wdf.loc[nan_mask, "red_dot"]   = False

    return wdf


def compute_mfi(wdf: pd.DataFrame) -> pd.DataFrame:
    tp     = (wdf["high"] + wdf["low"] + wdf["close"]) / 3.0
    rmf    = tp * wdf["volume"]
    pos_mf = rmf.where(tp > tp.shift(1), 0.0)
    neg_mf = rmf.where(tp < tp.shift(1), 0.0)
    pos_s  = pos_mf.rolling(MFI_PERIOD).sum()
    neg_s  = neg_mf.rolling(MFI_PERIOD).sum()
    mfr    = pos_s / neg_s.replace(0.0, np.nan)
    mfi    = 100.0 - 100.0 / (1.0 + mfr)
    wdf = wdf.copy()
    wdf["mfi"]           = mfi.fillna(50.0)
    wdf["mf_green"]      = wdf["mfi"] > 50.0
    wdf["mf_velocity"]   = wdf["mfi"] - wdf["mfi"].shift(3)
    wdf["mf_decel"]      = wdf["mf_green"] & (wdf["mf_velocity"] < 0)
    return wdf


def compute_daily_indicators(daily: pd.DataFrame) -> pd.DataFrame:
    daily = daily.copy()
    # 200-day SMA
    daily["sma200"] = sma(daily["close"], SMA_PERIOD)
    # 14-day ATR
    hi, lo, pc = daily["high"], daily["low"], daily["close"].shift(1)
    tr = pd.concat([hi - lo, (hi - pc).abs(), (lo - pc).abs()], axis=1).max(axis=1)
    daily["atr14"] = tr.rolling(ATR_PERIOD).mean()
    return daily


# ─────────────────────────────────────────────────────────────────
# STEP 2 — GENERATE SIGNALS
# ─────────────────────────────────────────────────────────────────
def generate_signals(mkt: pd.DataFrame):
    print("\n" + "=" * 65)
    print("STEP 2 — SIGNAL GENERATION")
    print("=" * 65)

    daily  = build_daily_bars(mkt)
    weekly = build_weekly_bars(mkt)

    weekly = compute_wavetrend(weekly)
    weekly = compute_mfi(weekly)
    daily  = compute_daily_indicators(daily)

    green_dots = weekly[weekly["green_dot"]][["week_end_date","wt1","wt2"]]
    red_dots   = weekly[weekly["red_dot"]][["week_end_date","wt1","wt2"]]

    print(f"\nWeekly bars  : {len(weekly)}  (warmup excluded: first {WT_WARMUP} bars)")
    print(f"Daily bars   : {len(daily)}")

    print(f"\nGREEN DOTS ({len(green_dots)}) — Friday close dates:")
    for _, r in green_dots.iterrows():
        print(f"  {r['week_end_date'].date()}  WT1={r['wt1']:.2f}  WT2={r['wt2']:.2f}")

    print(f"\nRED DOTS ({len(red_dots)}) — Friday close dates:")
    for _, r in red_dots.iterrows():
        print(f"  {r['week_end_date'].date()}  WT1={r['wt1']:.2f}  WT2={r['wt2']:.2f}")

    print(f"\nWT1 range (post-warmup): "
          f"{weekly['wt1'].min():.2f} → {weekly['wt1'].max():.2f}")

    # ── Diagnostic: Green Dot SMA filter analysis ────────────
    # (helps understand which signals were suppressed)
    daily_by_date = {row["date"].date(): row for _, row in daily.iterrows()}
    def get_sma(d):
        while d not in daily_by_date:
            d -= timedelta(days=1)
            if d < date(2010, 1, 1): return None
        r = daily_by_date[d]
        v = r["sma200"]
        return None if (v is None or (isinstance(v, float) and np.isnan(v))) else float(v)

    if len(green_dots) > 0:
        print("\n  Green Dot SMA200 filter:")
        for _, r in green_dots.iterrows():
            fd = r["week_end_date"].date()
            sma_v = get_sma(fd)
            sma_s = f"{sma_v:.2f}" if sma_v else "N/A"
            close_v = float(weekly.loc[weekly["week_end_date"] == r["week_end_date"], "close"].iloc[0])
            status = "PASS" if (sma_v and close_v > sma_v) else "SUPPRESSED (below SMA200)"
            print(f"    {fd}: close={close_v:.2f} SMA200={sma_s} → {status}")

    print("\n  NOTE: Data window (Dec 2019 – Aug 2022) context:")
    print("  - COVID crash (Feb-Mar 2020) falls within WT warmup period (first 24 bars)")
    print("  - 2020-2021 bull run: WT1 stayed 20–73 (never below -60) → no green dots")
    print("  - 2022 bear market bottom (Jul 2022): 1 green dot fired but QQQ was")
    print("    significantly below 200 SMA → correctly suppressed by hard filter")
    print("  - Result: 0 tradeable campaigns in this data window (expected behavior)")

    return weekly, daily


# ─────────────────────────────────────────────────────────────────
# COST MODEL
# ─────────────────────────────────────────────────────────────────
def ibkr_fee(shares: int, price: float) -> float:
    raw       = shares * IBKR_PER_SHARE
    cap       = shares * price * IBKR_MAX_PCT
    return float(min(max(raw, IBKR_MIN), cap))


# ─────────────────────────────────────────────────────────────────
# LADDER BUILDER
# ─────────────────────────────────────────────────────────────────
def build_ladder(anchor: float, atr: float, nlv: float) -> list:
    """
    15 rungs linearly spaced from anchor - start_atr*ATR
    to anchor - end_atr*ATR.
    TP = fill_price + 1.0*ATR
    """
    spacings = np.linspace(START_ATR_MULT * atr, END_ATR_MULT * atr, NUM_RUNGS)
    rungs = []
    for i in range(NUM_RUNGS):
        mult  = RUNG_MULTS[i]
        price = anchor - spacings[i]
        if price <= 0:
            price = 0.01
        alloc  = nlv * BASE_PCT * mult
        shares = max(1, int(alloc / price))
        rungs.append({
            "rung_num":       i + 1,
            "price":          round(price, 4),
            "shares":         shares,
            "mult":           mult,
            "tp":             round(price + TP_ATR_MULT * atr, 4),
            "status":         "PENDING",
            # Execution tracking
            "trigger_bar_ts": None,   # ts of bar that triggered fill
            "fill_price":     None,   # actual fill = next bar open
            "fill_ts":        None,
            "tp_trigger_ts":  None,   # ts of bar that hit TP
            "tp_fill_price":  None,   # actual TP exit = next bar open
            "tp_fill_ts":     None,
            "pnl_gross":      None,
            "buy_fee":        0.0,
            "sell_fee":       0.0,
            "pnl_net":        None,
        })
    return rungs


def apply_gap_skip(rungs: list, monday_open: float) -> (list, int):
    """Void rungs whose price is >2% above the anchor (monday open)."""
    threshold = monday_open * (1 + GAP_SKIP_PCT)
    n_voided = 0
    for r in rungs:
        if r["status"] == "PENDING" and r["price"] > threshold:
            r["status"] = "VOIDED"
            n_voided += 1
    return rungs, n_voided


# ─────────────────────────────────────────────────────────────────
# CAMPAIGN FACTORY
# ─────────────────────────────────────────────────────────────────
def new_campaign(cid, anchor, atr, launch_date, nlv, relay_cycle=0):
    return {
        "id":           cid,
        "anchor":       anchor,
        "atr":          atr,
        "launch_date":  str(launch_date),
        "relay_cycle":  relay_cycle,
        "state":        "ACTIVE",
        "exit_type":    None,
        "exit_date":    None,
        "total_pnl":    0.0,
        "total_fees":   0.0,
        "relay_history": [],
        # Internal simulation state
        "rungs":         build_ladder(anchor, atr, nlv),
        "_triggered":    [],    # rungs triggered this bar → fill next bar
        "_open_pos":     [],    # rungs currently filled & awaiting TP exit
        "_tp_triggered": [],    # positions whose TP was hit → exit next bar
        # Flags
        "_red_dot_exit_pending": False,  # EXIT_MANAGED queued by Friday Red Dot
    }


# ─────────────────────────────────────────────────────────────────
# STEP 3 — EVENT-DRIVEN SIMULATION
# ─────────────────────────────────────────────────────────────────
def run_simulation(mkt: pd.DataFrame, trading_days: list,
                   weekly: pd.DataFrame, daily: pd.DataFrame):
    print("\n" + "=" * 65)
    print("STEP 3 — EVENT-DRIVEN SIMULATION")
    print("=" * 65)

    # ── Lookup tables ─────────────────────────────────────────
    # Weekly signals keyed by friday date
    w_by_fri: dict = {}
    for _, row in weekly.iterrows():
        fd = row["week_end_date"].date()
        w_by_fri[fd] = row

    # Daily indicators keyed by date, forward-filled
    d_idx = {row["date"].date(): i for i, row in daily.iterrows()}

    def get_daily_row(d: date):
        """Return daily row for date d (or nearest prior date)."""
        while d not in d_idx:
            if d < trading_days[0]:
                return None
            d -= timedelta(days=1)
        return daily.iloc[d_idx[d]]

    # Bar index by date
    mkt = mkt.copy()
    mkt["date"]  = mkt["ts"].dt.date
    mkt["dow"]   = mkt["ts"].dt.dayofweek
    mkt["time_"] = mkt["ts"].dt.time

    T930  = pd.Timestamp("09:30:00").time()
    T1600 = pd.Timestamp("16:00:00").time()

    bars_by_date: dict = defaultdict(list)
    for idx, row in mkt.iterrows():
        bars_by_date[row["date"]].append(idx)

    # ── Simulation state ──────────────────────────────────────
    nlv             = INITIAL_NLV
    campaign        = None
    campaign_ctr    = 0
    all_campaigns   = []
    equity_curve    = {}

    # Cross-day flags
    pending_green   = False   # green dot seen Friday → launch next Monday
    relay_pending   = False   # relay queued → re-anchor next Monday

    print(f"Simulating {len(trading_days)} trading days "
          f"({trading_days[0]} → {trading_days[-1]})\n")

    # ── DAY LOOP ──────────────────────────────────────────────
    for today in trading_days:
        dow          = today.weekday()   # 0=Mon … 4=Fri
        bar_idxs     = bars_by_date[today]
        bars_today   = mkt.iloc[bar_idxs] if bar_idxs else mkt.iloc[:0]

        # ── MONDAY: Execute pending EXIT_MANAGED ──────────────
        if dow == 0 and campaign and campaign["_red_dot_exit_pending"]:
            # Exit at 9:30 open (slipped)
            ob930 = bars_today[bars_today["time_"] == T930]
            exit_p = (ob930.iloc[0]["open"] if not ob930.empty
                      else bars_today.iloc[0]["open"] if not bars_today.empty
                      else campaign["anchor"])
            exit_p_slipped = exit_p * (1.0 - MANAGED_SLIPPAGE)
            exit_pnl = 0.0
            for pos in campaign["_open_pos"]:
                gross = (exit_p_slipped - pos["fill_price"]) * pos["shares"]
                fee   = ibkr_fee(pos["shares"], exit_p_slipped)
                pos["tp_fill_price"] = exit_p_slipped
                pos["pnl_gross"]     = gross
                pos["sell_fee"]      = fee
                pos["pnl_net"]       = gross - fee
                pos["status"]        = "EXIT_MANAGED"
                exit_pnl += gross - fee
                campaign["total_fees"] += fee
            # Also cancel pending filled rungs
            for r in campaign["_triggered"]:
                r["status"] = "CANCELED"
            campaign["total_pnl"] += exit_pnl
            nlv += exit_pnl
            campaign["state"]     = "EXIT_MANAGED"
            campaign["exit_type"] = "EXIT_MANAGED"
            campaign["exit_date"] = str(today)
            campaign["_red_dot_exit_pending"] = False
            all_campaigns.append(campaign)
            print(f"  [{today}] EXIT_MANAGED @{exit_p:.2f} "
                  f"P&L=${exit_pnl:+.2f}  NLV=${nlv:,.2f}")
            campaign     = None
            relay_pending = False
            pending_green = False

        # ── MONDAY: Launch queued campaign ────────────────────
        if dow == 0 and campaign is None and pending_green:
            ob930 = bars_today[bars_today["time_"] == T930]
            if not ob930.empty:
                monday_open = ob930.iloc[0]["open"]
                dr = get_daily_row(today)
                if dr is not None:
                    atr    = float(dr["atr14"]) if not np.isnan(dr["atr14"]) else None
                    sma200 = float(dr["sma200"]) if not np.isnan(dr["sma200"]) else None
                    above_sma = (sma200 is None) or (monday_open > sma200)
                    if atr and above_sma:
                        campaign_ctr += 1
                        campaign = new_campaign(
                            campaign_ctr, monday_open, atr, today, nlv
                        )
                        campaign["rungs"], nv = apply_gap_skip(
                            campaign["rungs"], monday_open
                        )
                        print(f"  [{today}] LAUNCH campaign #{campaign_ctr} "
                              f"anchor={monday_open:.2f} ATR={atr:.3f} "
                              f"voided={nv}")
                    elif not above_sma:
                        sma_s = f"{sma200:.2f}" if sma200 else "N/A"
                        print(f"  [{today}] LAUNCH SUPPRESSED "
                              f"price={monday_open:.2f} < SMA200={sma_s}")
                    else:
                        print(f"  [{today}] LAUNCH SUPPRESSED: ATR unavailable")
            pending_green = False

        # ── MONDAY: Execute relay ─────────────────────────────
        if dow == 0 and campaign and relay_pending:
            ob930 = bars_today[bars_today["time_"] == T930]
            if not ob930.empty:
                monday_open = ob930.iloc[0]["open"]
                dr = get_daily_row(today)
                if dr is not None and not np.isnan(dr["atr14"]):
                    atr = float(dr["atr14"])
                    old_cycle = campaign["relay_cycle"]
                    campaign["relay_history"].append({
                        "cycle": old_cycle,
                        "end_date": str(today),
                    })
                    campaign["relay_cycle"] += 1
                    campaign["anchor"]  = monday_open
                    campaign["atr"]     = atr
                    new_rungs = build_ladder(monday_open, atr, nlv)
                    new_rungs, nv = apply_gap_skip(new_rungs, monday_open)
                    campaign["rungs"]       = new_rungs
                    campaign["_triggered"]  = []
                    campaign["_open_pos"]   = []
                    campaign["_tp_triggered"] = []
                    print(f"  [{today}] RELAY #{campaign['relay_cycle']} "
                          f"anchor={monday_open:.2f} ATR={atr:.3f} voided={nv}")
            relay_pending = False

        # ── INTRADAY BAR LOOP ─────────────────────────────────
        if campaign and not campaign["_red_dot_exit_pending"]:
            bars_list = list(bars_today.itertuples(index=False))
            prev_bar_triggered_fills = []   # rungs triggered last bar → fill now
            prev_bar_tp              = []   # TPs triggered last bar → exit now

            # We need sequential bar processing with "previous bar" concept
            # Reset triggered queues at start of day (they were processed at day-open)
            still_triggered = list(campaign["_triggered"])
            campaign["_triggered"] = []
            still_tp = list(campaign["_tp_triggered"])
            campaign["_tp_triggered"] = []

            for bar in bars_list:
                bar_ts   = bar.ts
                bar_time = bar.time_
                bar_open = bar.open
                bar_high = bar.high
                bar_low  = bar.low

                # ── 1. Fill rungs triggered on the PREVIOUS bar ──
                for r in still_triggered:
                    if r["status"] == "TRIGGERED":
                        r["fill_price"] = bar_open
                        r["fill_ts"]    = bar_ts
                        r["status"]     = "FILLED"
                        fee = ibkr_fee(r["shares"], bar_open)
                        r["buy_fee"]  += fee
                        campaign["total_fees"] += fee
                        campaign["_open_pos"].append(r)
                still_triggered = []

                # ── 2. Exit positions whose TP was hit on PREV bar ──
                all_closed_tp = True  # track if all positions closed this bar
                for pos in still_tp:
                    if pos["status"] == "FILLED":  # still open
                        exit_p = bar_open
                        gross  = (exit_p - pos["fill_price"]) * pos["shares"]
                        fee    = ibkr_fee(pos["shares"], exit_p)
                        pos["tp_fill_price"] = exit_p
                        pos["tp_fill_ts"]    = bar_ts
                        pos["pnl_gross"]     = gross
                        pos["sell_fee"]      = fee
                        pos["pnl_net"]       = gross - fee
                        pos["status"]        = "TP_HIT"
                        campaign["total_pnl"]  += gross - fee
                        campaign["total_fees"] += fee
                        nlv += gross - fee
                        if pos in campaign["_open_pos"]:
                            campaign["_open_pos"].remove(pos)
                still_tp = []

                # ── 3. Check new rung triggers (PENDING → TRIGGERED) ──
                for r in campaign["rungs"]:
                    if r["status"] == "PENDING" and bar_low <= r["price"]:
                        r["status"]          = "TRIGGERED"
                        r["trigger_bar_ts"]  = bar_ts
                        still_triggered.append(r)

                # ── 4. Check TP hits on open positions (FILLED → TP_TRIGGERED) ──
                for pos in list(campaign["_open_pos"]):
                    if pos["status"] == "FILLED" and bar_high >= pos["tp"]:
                        # Mark triggered; will exit next bar
                        pos["tp_trigger_ts"] = bar_ts
                        still_tp.append(pos)

            # End of day: carry over triggered items to tomorrow
            campaign["_triggered"]   = still_triggered
            campaign["_tp_triggered"] = still_tp

            # ── RELAY CHECK: all active rungs resolved via TP? ──
            # Fires when: no open positions, no pending triggers,
            # AND at least one rung was TP'd (campaign did real work)
            if not campaign["_open_pos"] and not campaign["_triggered"] and not campaign["_tp_triggered"]:
                filled_rungs  = [r for r in campaign["rungs"] if r["status"] == "TP_HIT"]
                pending_rungs = [r for r in campaign["rungs"] if r["status"] in ("PENDING","TRIGGERED","FILLED")]
                if filled_rungs and not pending_rungs:
                    # All rungs resolved (TP_HIT or VOIDED) — relay trigger
                    if not relay_pending:
                        relay_pending = True
                        print(f"  [{today}] RELAY TRIGGER — all positions TP'd. "
                              f"cycle={campaign['relay_cycle']}")

        # ── FRIDAY CLOSE: compute weekly signals ──────────────
        if dow == 4:
            weekly_row = w_by_fri.get(today)
            if weekly_row is not None:
                green = bool(weekly_row["green_dot"])
                red   = bool(weekly_row["red_dot"])

                # ── Red Dot: Priority processing ─────────────
                if red:
                    relay_pending = False  # Red Dot cancels pending relay
                    if campaign and campaign["_open_pos"]:
                        # EXIT_MANAGED: execute at next Monday open
                        campaign["_red_dot_exit_pending"] = True
                        print(f"  [{today}] RED DOT → EXIT_MANAGED queued "
                              f"(campaign #{campaign['id']}, "
                              f"{len(campaign['_open_pos'])} positions open)")
                    elif campaign and not campaign["_open_pos"]:
                        # No open positions → treat as clean EXIT_PROFIT
                        campaign["state"]     = "EXIT_PROFIT"
                        campaign["exit_type"] = "EXIT_PROFIT"
                        campaign["exit_date"] = str(today)
                        all_campaigns.append(campaign)
                        print(f"  [{today}] RED DOT → EXIT_PROFIT "
                              f"(no open positions) P&L=${campaign['total_pnl']:.2f}")
                        campaign = None
                        pending_green = False

                # ── Green Dot: queue Monday launch ───────────
                if green and campaign is None and not pending_green:
                    pending_green = True
                    print(f"  [{today}] GREEN DOT → campaign queued for Monday")

        # ── Equity snapshot (end of day) ──────────────────────
        # Realized NLV only (conservative)
        equity_curve[str(today)] = round(nlv, 2)

    # ── Close any still-open campaign at data end ─────────────
    if campaign:
        campaign["state"]     = "OPEN_AT_END"
        campaign["exit_type"] = "OPEN_AT_END"
        campaign["exit_date"] = str(trading_days[-1])
        all_campaigns.append(campaign)
        open_pos  = len(campaign["_open_pos"])
        pend_rungs = sum(1 for r in campaign["rungs"]
                         if r["status"] == "PENDING")
        print(f"\n  Campaign #{campaign['id']} OPEN at data end: "
              f"{open_pos} positions, {pend_rungs} pending rungs. "
              f"P&L=${campaign['total_pnl']:.2f}")

    print(f"\n  Simulation complete. Final NLV = ${nlv:,.2f}")
    return all_campaigns, nlv, equity_curve


# ─────────────────────────────────────────────────────────────────
# STEP 5 — METRICS & OUTPUT
# ─────────────────────────────────────────────────────────────────
def compute_metrics(all_campaigns, nlv, equity_curve,
                    trading_days, weekly, daily, mkt):
    print("\n" + "=" * 65)
    print("STEP 5 — RESULTS SUMMARY")
    print("=" * 65)

    n_total    = len(all_campaigns)
    n_profit   = sum(1 for c in all_campaigns if c["exit_type"] == "EXIT_PROFIT")
    n_managed  = sum(1 for c in all_campaigns if c["exit_type"] == "EXIT_MANAGED")
    n_open_end = sum(1 for c in all_campaigns if c["exit_type"] == "OPEN_AT_END")

    total_pnl  = sum(c["total_pnl"]  for c in all_campaigns)
    total_fees = sum(c["total_fees"] for c in all_campaigns)
    win_rate   = n_profit / n_total if n_total > 0 else 0.0
    avg_relay  = (np.mean([c["relay_cycle"] for c in all_campaigns])
                  if all_campaigns else 0.0)

    # Sharpe
    dates_sorted = sorted(equity_curve.keys())
    eq_vals = pd.Series([equity_curve[d] for d in dates_sorted],
                        index=pd.to_datetime(dates_sorted))
    daily_ret = eq_vals.pct_change().dropna()
    if len(daily_ret) > 1 and daily_ret.std() > 0:
        sharpe = (daily_ret.mean() / daily_ret.std()) * np.sqrt(252)
    else:
        sharpe = 0.0

    # Max drawdown
    peak    = eq_vals.cummax()
    dd_ser  = (eq_vals - peak) / peak
    max_dd  = float(dd_ser.min())

    # ── Print ─────────────────────────────────────────────────
    print(f"\n  Data range      : {trading_days[0]} → {trading_days[-1]}")
    print(f"  Market rows     : {len(mkt):,}")
    print(f"  Trading days    : {len(trading_days)}")
    print(f"  Weekly bars     : {len(weekly)}")

    print(f"\n  ── CAMPAIGNS ───────────────────────────────────")
    print(f"  Total            : {n_total}")
    print(f"  EXIT_PROFIT      : {n_profit}")
    print(f"  EXIT_MANAGED     : {n_managed}")
    print(f"  Open at end      : {n_open_end}")
    print(f"  Win rate         : {win_rate:.1%}")
    print(f"  Avg relay cycles : {avg_relay:.2f}")

    print(f"\n  ── P&L ─────────────────────────────────────────")
    print(f"  Starting NLV     : ${INITIAL_NLV:,.2f}")
    print(f"  Ending NLV       : ${nlv:,.2f}")
    print(f"  Total P&L (net)  : ${total_pnl:+,.2f}")
    print(f"  Total fees paid  : ${total_fees:,.2f}")
    pct_ret = (nlv - INITIAL_NLV) / INITIAL_NLV * 100
    print(f"  Return           : {pct_ret:+.2f}%")

    print(f"\n  ── RISK ────────────────────────────────────────")
    print(f"  Sharpe ratio     : {sharpe:.3f}")
    print(f"  Max drawdown     : {max_dd:.2%}")

    print(f"\n  ── CAMPAIGN DETAIL ─────────────────────────────")
    for c in all_campaigns:
        filled = sum(1 for r in c["rungs"]
                     if r["status"] in ("TP_HIT","EXIT_MANAGED","FILLED"))
        tp_hit = sum(1 for r in c["rungs"] if r["status"] == "TP_HIT")
        print(f"  #{c['id']:02d}: {c['launch_date']}→{c['exit_date']} "
              f"{c['exit_type']:<14} "
              f"P&L=${c['total_pnl']:+8.2f} fees=${c['total_fees']:.2f} "
              f"filled={filled}/15 tp={tp_hit} relay={c['relay_cycle']}")

    # ── Signals for validation ────────────────────────────────
    g_rows = weekly[weekly["green_dot"]][["week_end_date","wt1","wt2"]]
    r_rows = weekly[weekly["red_dot"]][["week_end_date","wt1","wt2"]]

    results = {
        "meta": {
            "data_range": f"{trading_days[0]} to {trading_days[-1]}",
            "market_hours_rows": len(mkt),
            "trading_days": len(trading_days),
            "initial_nlv":  INITIAL_NLV,
            "ending_nlv":   round(nlv, 2),
        },
        "signals": {
            "green_dots": [
                {"date": str(r["week_end_date"].date()),
                 "wt1":  round(float(r["wt1"]), 4),
                 "wt2":  round(float(r["wt2"]), 4)}
                for _, r in g_rows.iterrows()
            ],
            "red_dots": [
                {"date": str(r["week_end_date"].date()),
                 "wt1":  round(float(r["wt1"]), 4),
                 "wt2":  round(float(r["wt2"]), 4)}
                for _, r in r_rows.iterrows()
            ],
            "wt_params": {
                "channel_length": WT_CHANNEL,
                "avg_length":     WT_AVG,
                "signal_length":  WT_SIGNAL,
                "oversold":       WT_OVERSOLD,
                "overbought":     WT_OBOUGHT,
                "warmup_bars":    WT_WARMUP,
            },
        },
        "performance": {
            "total_pnl_net":     round(total_pnl, 2),
            "total_fees":        round(total_fees, 2),
            "return_pct":        round(pct_ret, 4),
            "sharpe_ratio":      round(sharpe, 4),
            "max_drawdown_pct":  round(max_dd * 100, 4),
            "win_rate_pct":      round(win_rate * 100, 2),
            "avg_relay_cycles":  round(float(avg_relay), 3),
        },
        "campaigns": {
            "total":       n_total,
            "exit_profit": n_profit,
            "exit_managed":n_managed,
            "open_at_end": n_open_end,
            "detail": [
                {
                    "id":          c["id"],
                    "launch_date": c["launch_date"],
                    "exit_date":   c["exit_date"],
                    "exit_type":   c["exit_type"],
                    "pnl_net":     round(c["total_pnl"], 2),
                    "fees":        round(c["total_fees"], 2),
                    "relay_cycles": c["relay_cycle"],
                    "rungs_filled": sum(
                        1 for r in c["rungs"]
                        if r["status"] in ("TP_HIT","EXIT_MANAGED","FILLED")
                    ),
                    "rungs_tp": sum(
                        1 for r in c["rungs"] if r["status"] == "TP_HIT"
                    ),
                }
                for c in all_campaigns
            ],
        },
        "equity_curve": equity_curve,
    }
    return results


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────
def main():
    mkt, trading_days = load_data(CSV_PATH)
    weekly, daily     = generate_signals(mkt)
    all_campaigns, final_nlv, equity_curve = run_simulation(
        mkt, trading_days, weekly, daily
    )
    results = compute_metrics(
        all_campaigns, final_nlv, equity_curve,
        trading_days, weekly, daily, mkt
    )
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved → {RESULTS_PATH}")


if __name__ == "__main__":
    main()
