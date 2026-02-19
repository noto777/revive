# IronHand Live Bot - Complete Codebase Analysis

## Source: `G:\Projects\Personal\Core_Strategy_Live`
## Date: Feb 15, 2026

---

## Architecture Overview

The live bot is a **monolithic Python trading application** for Interactive Brokers (IBKR) that implements a dip-buying strategy with ATR-based ladder entries, core position management, and automated sell strategies.

### Core Files (28 Python files, ~5,500 LOC in core modules)

| File | LOC (est) | Purpose |
|------|-----------|---------|
| `main.py` | ~2,200 | `DipBuyingStrategy` class - main orchestrator |
| `config.py` | ~200 | Central configuration (params, logging, Telegram) |
| `strategy_logic.py` | ~90 | `CoreStrategyLogic` - ladder generation with curved ATR multipliers |
| `core_manager.py` | ~170 | `CorePositionManager` - exit strategies (rebalancing, scale-out, profit lock) |
| `indicator_engine.py` | ~120 | RSI, BBands, ATR, WaveTrend calculations (pandas/numpy/scipy) |
| `db_manager.py` | ~200 | `DBManager` - thread-safe SQLite singleton with WAL mode |
| `ibapi_client.py` | ~700 | `IBApiApp` - IBKR TWS API wrapper (EClient/EWrapper) |
| `webapp.py` | ~130 | Flask dashboard (port 5002) with command IPC via DB |
| `sqlite_manager.py` | ~200 | **DUPLICATE** DB layer (older, separate from db_manager.py) |
| `rest_client.py` | ~40 | Client Portal REST test script |
| `client_portal_client.py` | ~250 | Full Client Portal Web API wrapper |
| `exceptions.py` | ~100 | Typed exception hierarchy |

### Utility/One-off Scripts
- `check_positions.py`, `db_inspector.py`, `download_data.py`, `find_culprits.py`
- `generate_snapshot.py`, `getchamps.py`, `main_backtest.py`, `migrate_db.py`
- `migration.py`, `optimize_portfolio.py`, `preserve.py`, `reset_positions.py`
- `setup_workspace.py`, `validate_orders.py`, `verifypnl.py`

---

## Key Design Patterns

### 1. Strategy Loop (main.py - `DipBuyingStrategy`)
- Connects to IBKR TWS via `ibapi_client`
- 15-second check interval (`CHECK_INTERVAL`)
- Each cycle: fetch indicators → determine regime → manage ladder → check fills → manage sells → update dashboard
- Telegram notifications for trades, errors, status updates (30-min intervals)

### 2. Hysteresis Regime System
Three regimes based on RSI with hysteresis thresholds:
- **AGGRESSIVE** (RSI < 30): Wider ladder spread, more rungs
- **NEUTRAL** (RSI 40-60): Standard parameters
- **DEFENSIVE** (RSI > 70): Tighter spread

Note: All three regimes currently have **identical parameters** (start_atr=0.2, end_atr=0.6, curve=1.0, size_factor=1.25), making the regime system effectively a no-op.

### 3. Ladder Generation (strategy_logic.py)
- **Look-ahead sizing**: Tries max slots down to 1, finding the optimal count where the smallest trade meets `MIN_LADDER_TRADE_VALUE_USD` ($500)
- Curved ATR multipliers via `np.linspace` with power curve
- Size increase factor ramps up notional value for deeper rungs
- Fixed division-by-zero bug for single-slot case

### 4. Core Position Management (core_manager.py)
Two-mode exit strategy:
- **Rebalancing Mode**: When core allocation exceeds `MAX_CORE_PERCENT_ACCOUNT + CORE_HYSTERESIS_GAP` (17%), trim 5% at each 2% profit step
- **Standard Scale-Out Mode**: Sell 15% at each 4% profit step starting at 8%
- **Universal Profit Lock**: Arms at 12% profit, trails by 4%, sells all if triggered

### 5. Database (SQLite with WAL)
Tables: `positions`, `orders`, `processed_executions`, `dashboard_state`, `commands`, `processed_phantom_fills`, `strategy_state`
- **IPC Pattern**: Webapp writes to `commands` table, bot polls for unprocessed commands
- Dashboard state written as JSON blob per symbol

### 6. Dual API Architecture
- **Primary**: TWS API via `ibapi_client.py` (EClient/EWrapper pattern, port 7496)
- **Secondary**: Client Portal REST API via `client_portal_client.py` (HTTPS localhost:5000)
- Connection retry with exponential backoff (3 attempts, 2s base)

---

## Critical Issues Found

### 🔴 HIGH: Duplicate DB Layer
`sqlite_manager.py` and `db_manager.py` are **separate implementations** of the same thing:
- `db_manager.py`: Thread-safe singleton, transaction context manager, WAL mode
- `sqlite_manager.py`: Simple connection-per-call, commit-on-close pattern
- `webapp.py` imports `DBManager` from `db_manager.py`
- Unknown which files use `sqlite_manager.py` (need to check main.py imports)
- **Risk**: Two different connection patterns to the same SQLite file = potential corruption

### 🔴 HIGH: Identical Regime Parameters
All three hysteresis regimes (AGGRESSIVE, NEUTRAL, DEFENSIVE) have identical config:
```python
'start_atr': 0.2, 'end_atr': 0.6, 'distribution_curve': 1.0, 'size_increase_factor': 1.25
```
The entire regime system is dead code — it calculates RSI, determines regime, but uses the same params regardless.

### 🟡 MEDIUM: Hardcoded Contract Details
- `ibapi_client.py` defaults to `secType="STK"`, `exchange="SMART"`, `primaryExchange="ISLAND"`
- But the bot trades ETHU (a leveraged ETF) — should verify contract routing
- `create_stock_contract()` has a fallback that may not work for all instruments

### 🟡 MEDIUM: No Graceful Shutdown
- The main loop uses `time.sleep(15)` between checks
- No signal handlers visible in the truncated main.py
- Unclear if there's cleanup on CTRL+C (DB connections, open orders, IB disconnect)

### 🟡 MEDIUM: Dashboard State as JSON Blob
- Entire dashboard state serialized as JSON string in SQLite
- No indexing on positions within the state
- Webapp filters CLOSED positions client-side after deserializing

### 🟢 LOW: Dual RSI Implementations
- `indicator_engine.py` has `_calculate_rsi_series()` (EWM-based)
- `ibapi_client.py` has `compute_rsi()` (rolling + EWM hybrid)
- Different algorithms may produce slightly different values

### 🟢 LOW: Print Statements vs Logging
- `ibapi_client.py` mixes `print()` with `logger.info()` throughout
- Some callbacks use print exclusively (position, order status)

---

## SaaS Refactor Considerations

### What to Keep (Good Patterns)
1. **Exception hierarchy** (exceptions.py) — clean, typed, useful
2. **DBManager singleton with WAL** — solid for single-process
3. **Strategy logic separation** — `CoreStrategyLogic` and `CorePositionManager` are well-isolated
4. **Indicator engine** — pure functions, no side effects
5. **Retry logic with backoff** — `get_ibkr_connection_with_retry()`

### What Needs Major Refactoring
1. **DB layer consolidation** — pick one, delete the other
2. **Regime system** — either differentiate the params or remove the abstraction
3. **IB client decoupling** — too many responsibilities (connection, data, orders, market data)
4. **Config as module-level globals** — needs to become instance config for multi-tenant
5. **Telegram notifications** — hardcoded bot token/chat — needs per-user routing
6. **Flask dashboard** — tightly coupled to SQLite, needs API layer for SaaS

### Architecture for SaaS
The current monolith runs ONE instance for ONE account trading ONE symbol (ETHU).
For SaaS:
- **Multi-tenant**: Config per user, isolated DB per tenant or schema isolation
- **Broker abstraction**: IB-specific code behind an interface (for Alpaca, etc.)
- **Event-driven**: Replace polling loop with event system
- **API-first**: Dashboard becomes a frontend consuming REST/WebSocket API
- **Queue-based**: Order execution through a job queue, not inline

---

## File Inventory (Non-venv)

### Core Application
```
main.py              # Main strategy orchestrator
config.py            # Configuration and logging setup
strategy_logic.py    # Ladder generation algorithm
core_manager.py      # Core position exit strategies
indicator_engine.py  # Technical indicators (RSI, BBands, ATR, WaveTrend)
db_manager.py        # Primary SQLite DB manager (singleton, thread-safe)
sqlite_manager.py    # Legacy SQLite manager (SHOULD BE REMOVED)
ibapi_client.py      # IBKR TWS API client and helpers
client_portal_client.py  # IBKR Client Portal REST API
webapp.py            # Flask web dashboard
rest_client.py       # Client Portal connection test
exceptions.py        # Custom exception classes
```

### Utility Scripts
```
check_positions.py   # Position inspection tool
db_inspector.py      # Database inspection
download_data.py     # Historical data downloader
find_culprits.py     # Debug tool
generate_snapshot.py # State snapshot generator
getchamps.py         # Unknown purpose
main_backtest.py     # Backtesting harness
migrate_db.py        # Database migration
migration.py         # Schema migration
optimize_portfolio.py # Portfolio optimization (cvxpy)
preserve.py          # State preservation
reset_positions.py   # Position reset tool
setup_workspace.py   # Workspace setup
validate_orders.py   # Order validation
verifypnl.py         # P&L verification
```

### Supporting Files
```
.env                 # Secrets (Telegram token, chat ID)
dip_strategy.db      # SQLite database
run_bot.bat          # Windows launcher
```

### Dependencies (from venv)
Key packages: ibapi, ib_insync, flask, pandas, numpy, scipy, backtrader, plotly, matplotlib, cvxpy, pytz, colorama, python-dotenv, requests, httpx, coinbase, cryptography, beautifulsoup4
