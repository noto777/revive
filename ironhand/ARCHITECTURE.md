# IronHand SaaS Architecture

## Overview

Refactor from a single-user monolith into a multi-tenant SaaS platform. The core trading logic is solid and stays largely intact — the work is in decoupling, isolating tenants, and exposing everything through APIs.

---

## Module Structure

```
ironhand/
├── api/                        # FastAPI application
│   ├── app.py                  # App factory, middleware, lifespan
│   ├── auth.py                 # JWT auth, API keys, tenant resolution
│   ├── routes/
│   │   ├── strategies.py       # CRUD strategies, start/stop/pause
│   │   ├── positions.py        # Position queries, manual overrides
│   │   ├── orders.py           # Order history, cancel
│   │   ├── dashboard.py        # Dashboard state, WebSocket feed
│   │   ├── accounts.py         # User/tenant management
│   │   └── webhooks.py         # Telegram/notification config
│   └── websocket.py            # Real-time dashboard push
│
├── core/                       # Pure business logic (no I/O)
│   ├── strategy_logic.py       # Ladder generation (from existing)
│   ├── core_manager.py         # Exit strategies (from existing)
│   ├── indicators.py           # RSI, BBands, ATR, WaveTrend (from existing)
│   └── risk.py                 # Position sizing, exposure limits
│
├── engine/                     # Strategy execution runtime
│   ├── executor.py             # Per-tenant strategy loop (replaces main.py)
│   ├── scheduler.py            # Manages executor lifecycle across tenants
│   ├── signals.py              # Graceful shutdown (SIGTERM/SIGINT handlers)
│   └── events.py               # Internal event bus (fills, errors, state changes)
│
├── brokers/                    # Broker abstraction layer
│   ├── base.py                 # Abstract broker interface
│   ├── ibkr_tws.py             # IBKR TWS (from ibapi_client.py)
│   ├── ibkr_portal.py          # IBKR Client Portal REST
│   └── paper.py                # Paper trading / simulation
│
├── notifications/              # Notification abstraction
│   ├── base.py                 # Abstract notifier
│   ├── telegram.py             # Telegram (from existing)
│   ├── webhook.py              # Generic webhook
│   └── dispatcher.py           # Routes events → user's configured channels
│
├── db/                         # Single unified data layer
│   ├── models.py               # SQLAlchemy models
│   ├── session.py              # Session factory, per-tenant routing
│   ├── migrations/             # Alembic migrations
│   └── queries.py              # Common query patterns
│
├── config.py                   # Pydantic Settings (env + per-tenant overrides)
├── exceptions.py               # Exception hierarchy (keep existing, extend)
└── logging.py                  # Structured logging (no more print())
```

**Key decisions:**
- **FastAPI** over Flask — async, WebSocket native, auto-docs, Pydantic validation
- **SQLAlchemy + Alembic** — proper ORM, migrations, broker-agnostic DB
- **PostgreSQL** in production — row-level tenant isolation, proper concurrency
- Delete `sqlite_manager.py` entirely — consolidate into `db/`

---

## Database Schema

```sql
-- Tenant isolation via tenant_id FK on every table

CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    api_key_hash    VARCHAR(255),
    plan            VARCHAR(20) DEFAULT 'free',  -- free, pro, enterprise
    max_strategies  INT DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT now(),
    is_active       BOOLEAN DEFAULT true
);

CREATE TABLE broker_connections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    broker_type     VARCHAR(20) NOT NULL,        -- ibkr_tws, ibkr_portal, paper
    config_enc      BYTEA NOT NULL,              -- encrypted JSON (host, port, client_id, etc.)
    is_active       BOOLEAN DEFAULT true,
    last_connected  TIMESTAMPTZ,
    UNIQUE(tenant_id, broker_type)
);

CREATE TABLE strategies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    broker_conn_id  UUID REFERENCES broker_connections(id),
    symbol          VARCHAR(20) NOT NULL,
    status          VARCHAR(20) DEFAULT 'stopped', -- stopped, running, paused, error
    config          JSONB NOT NULL,                -- all strategy params (replaces config.py globals)
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Config JSONB structure:
-- {
--   "check_interval": 15,
--   "min_ladder_trade_usd": 500,
--   "start_atr": 0.2,
--   "end_atr": 0.6,
--   "distribution_curve": 1.0,
--   "size_increase_factor": 1.25,
--   "max_core_pct": 15.0,
--   "core_hysteresis_gap": 2.0,
--   "scale_out_pct": 15.0,
--   "scale_out_step": 4.0,
--   "profit_lock_arm": 12.0,
--   "profit_lock_trail": 4.0
-- }

CREATE TABLE positions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id     UUID REFERENCES strategies(id) ON DELETE CASCADE,
    tenant_id       UUID REFERENCES tenants(id),
    symbol          VARCHAR(20) NOT NULL,
    entry_price     DECIMAL(18,8) NOT NULL,
    quantity        DECIMAL(18,8) NOT NULL,
    side            VARCHAR(4) NOT NULL,         -- LONG, SHORT
    status          VARCHAR(10) DEFAULT 'open',  -- open, closed, partial
    rung_index      INT,                         -- ladder rung that triggered this
    pnl_realized    DECIMAL(18,8) DEFAULT 0,
    opened_at       TIMESTAMPTZ DEFAULT now(),
    closed_at       TIMESTAMPTZ
);

CREATE TABLE orders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id     UUID REFERENCES strategies(id) ON DELETE CASCADE,
    tenant_id       UUID REFERENCES tenants(id),
    broker_order_id VARCHAR(100),
    symbol          VARCHAR(20) NOT NULL,
    side            VARCHAR(4) NOT NULL,
    order_type      VARCHAR(10) NOT NULL,        -- LMT, MKT, STP
    quantity        DECIMAL(18,8) NOT NULL,
    limit_price     DECIMAL(18,8),
    status          VARCHAR(20) NOT NULL,         -- pending, filled, partial, cancelled, error
    fill_price      DECIMAL(18,8),
    fill_quantity   DECIMAL(18,8),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE executions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id        UUID REFERENCES orders(id),
    tenant_id       UUID REFERENCES tenants(id),
    broker_exec_id  VARCHAR(100) UNIQUE,
    price           DECIMAL(18,8) NOT NULL,
    quantity        DECIMAL(18,8) NOT NULL,
    commission      DECIMAL(18,8) DEFAULT 0,
    executed_at     TIMESTAMPTZ NOT NULL
);

CREATE TABLE notification_channels (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    channel_type    VARCHAR(20) NOT NULL,         -- telegram, webhook, email
    config_enc      BYTEA NOT NULL,               -- encrypted (bot_token, chat_id, url, etc.)
    events          JSONB DEFAULT '["fill","error","status"]',
    is_active       BOOLEAN DEFAULT true
);

CREATE TABLE strategy_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id     UUID REFERENCES strategies(id) ON DELETE CASCADE,
    tenant_id       UUID REFERENCES tenants(id),
    snapshot        JSONB NOT NULL,               -- full dashboard state
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX idx_positions_strategy ON positions(strategy_id, status);
CREATE INDEX idx_orders_strategy ON orders(strategy_id, status);
CREATE INDEX idx_executions_tenant ON executions(tenant_id);
CREATE INDEX idx_strategies_tenant ON strategies(tenant_id, status);
```

**Regime system: removed.** The three regimes had identical params. Instead, strategy config is a flat JSONB blob that users can tune directly. If regime-like behavior is wanted later, it becomes a feature within `core/strategy_logic.py` that reads different param sets from the config.

---

## API Design

Base: `/api/v1`

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Create tenant account |
| POST | `/auth/login` | Get JWT token |
| POST | `/auth/api-key` | Generate API key |

### Strategies
| Method | Path | Description |
|--------|------|-------------|
| GET | `/strategies` | List tenant's strategies |
| POST | `/strategies` | Create strategy (symbol + config) |
| GET | `/strategies/{id}` | Get strategy detail + current state |
| PATCH | `/strategies/{id}` | Update config (hot-reload if running) |
| DELETE | `/strategies/{id}` | Delete (must be stopped) |
| POST | `/strategies/{id}/start` | Start execution |
| POST | `/strategies/{id}/stop` | Graceful stop |
| POST | `/strategies/{id}/pause` | Pause (keep state, stop trading) |

### Positions & Orders
| Method | Path | Description |
|--------|------|-------------|
| GET | `/strategies/{id}/positions` | List positions (filter: open/closed) |
| GET | `/strategies/{id}/orders` | Order history |
| POST | `/strategies/{id}/orders/{oid}/cancel` | Cancel open order |
| GET | `/strategies/{id}/dashboard` | Current dashboard snapshot |

### Broker Connections
| Method | Path | Description |
|--------|------|-------------|
| GET | `/brokers` | List tenant's broker connections |
| POST | `/brokers` | Add broker connection |
| POST | `/brokers/{id}/test` | Test connectivity |
| DELETE | `/brokers/{id}` | Remove |

### Notifications
| Method | Path | Description |
|--------|------|-------------|
| GET | `/notifications` | List notification channels |
| POST | `/notifications` | Add channel (telegram, webhook) |
| DELETE | `/notifications/{id}` | Remove |

### WebSocket
| Path | Description |
|------|-------------|
| `/ws/dashboard/{strategy_id}` | Real-time dashboard updates |
| `/ws/events` | All tenant events (fills, errors, status) |

---

## Component Interaction Flow

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (SPA)                     │
│              React / Next.js Dashboard                │
└──────────────────────┬──────────────────────────────┘
                       │ REST + WebSocket
                       ▼
┌─────────────────────────────────────────────────────┐
│                   FastAPI (api/)                      │
│  auth.py → routes/* → websocket.py                   │
│  JWT/API-key auth, tenant resolution middleware       │
└──────────┬───────────────────────┬──────────────────┘
           │                       │
           ▼                       ▼
┌──────────────────┐    ┌─────────────────────────────┐
│    db/ (SQLAlch)  │    │     engine/scheduler.py      │
│  PostgreSQL       │    │  Manages executor instances   │
│  All persistence  │◄──►│  One executor per strategy    │
└──────────────────┘    └──────────┬──────────────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │  engine/executor.py   │
                        │  Per-strategy loop    │
                        │  (replaces main.py)   │
                        └───┬─────────┬────────┘
                            │         │
                ┌───────────▼─┐   ┌───▼──────────────┐
                │  core/       │   │  brokers/          │
                │  strategy    │   │  base.py interface  │
                │  indicators  │   │  ibkr_tws.py impl   │
                │  risk        │   │  paper.py impl      │
                └──────────────┘   └────────────────────┘
                                          │
                                          ▼
                                   ┌──────────────┐
                                   │  IBKR TWS /   │
                                   │  Gateway       │
                                   └──────────────┘

Events flow:
  executor → events.py → dispatcher.py → telegram/webhook
  executor → events.py → websocket.py → frontend
  executor → db/ → persistence
```

### Executor Lifecycle

1. API receives `POST /strategies/{id}/start`
2. `scheduler.py` spawns an `Executor` (asyncio task or thread)
3. Executor loads strategy config from DB
4. Executor creates broker connection via `brokers/base.py` factory
5. Executor runs the 15-second loop: indicators → ladder → fills → sells → snapshot
6. All state changes go through `db/` and `events.py`
7. On `stop`: signal handler sets shutdown flag → executor finishes current cycle → disconnects broker → updates status

### Graceful Shutdown

```python
# engine/signals.py
class ShutdownManager:
    def __init__(self):
        self._shutdown = asyncio.Event()
        signal.signal(signal.SIGTERM, self._handle)
        signal.signal(signal.SIGINT, self._handle)

    def _handle(self, sig, frame):
        self._shutdown.set()

    async def wait(self):
        await self._shutdown.wait()
```

Each executor checks `shutdown_event.is_set()` at the top of its loop. No more naked `time.sleep(15)` — use `asyncio.wait_for(shutdown_event.wait(), timeout=15)`.

---

## Broker Abstraction

```python
# brokers/base.py
class BrokerInterface(ABC):
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def get_positions(self) -> list[Position]: ...

    @abstractmethod
    async def get_account_summary(self) -> AccountSummary: ...

    @abstractmethod
    async def place_order(self, order: OrderRequest) -> str: ...

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> None: ...

    @abstractmethod
    async def get_market_data(self, symbol: str, duration: str) -> pd.DataFrame: ...

    @abstractmethod
    def on_fill(self, callback: Callable[[Execution], None]) -> None: ...
```

`ibkr_tws.py` wraps the existing `ibapi_client.py` behind this interface. The dual RSI issue is resolved by using only `indicators.py` for all indicator calculations — the broker layer just provides raw OHLCV data.

---

## Logging

Replace all `print()` with structured logging:

```python
# logging.py
import structlog

def setup_logging(tenant_id: str = None):
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )

# Usage everywhere:
log = structlog.get_logger()
log.info("order_placed", symbol="ETHU", qty=10, tenant_id=tenant_id)
```

Every log line includes `tenant_id` for filtering. No more mixed print/logging.

---

## Migration Strategy

### Phase 1: Clean & Consolidate (no behavior change)
1. Delete `sqlite_manager.py` — audit all imports, point everything to `db_manager.py`
2. Remove regime system — flatten to single param set in config
3. Replace all `print()` with `logger.info/warning/error`
4. Add signal handlers for graceful shutdown
5. Extract `main.py` god-class into `executor.py` + `core/` modules
6. **Test**: Run refactored monolith against paper account, verify identical behavior

### Phase 2: Abstract & Isolate
1. Create `brokers/base.py` interface, wrap existing IB code in `ibkr_tws.py`
2. Move config from module globals to Pydantic models
3. Create `db/models.py` with SQLAlchemy, write migration from old SQLite schema
4. Add `events.py` internal event bus
5. **Test**: Same behavior, new structure

### Phase 3: API Layer
1. Build FastAPI app with auth
2. Implement all REST endpoints
3. Add WebSocket for dashboard
4. Replace Flask webapp entirely
5. **Test**: API-driven control of single strategy

### Phase 4: Multi-Tenant
1. Switch to PostgreSQL
2. Add tenant isolation (all queries scoped by tenant_id)
3. Scheduler manages multiple executors
4. Per-tenant broker connections and notification routing
5. Encrypt sensitive config (broker credentials, API keys)
6. **Test**: Two tenants running simultaneously, isolated

### Phase 5: Production Hardening
1. Rate limiting, request validation
2. Monitoring (Prometheus metrics per tenant)
3. Background task queue (Celery/ARQ) for heavy operations
4. Docker compose for local dev, Kubernetes manifests for prod
5. CI/CD pipeline

---

## What Stays, What Goes

| Keep As-Is | Refactor | Delete |
|------------|----------|--------|
| `strategy_logic.py` (→ `core/`) | `main.py` (→ `engine/executor.py`) | `sqlite_manager.py` |
| `core_manager.py` (→ `core/`) | `ibapi_client.py` (→ `brokers/ibkr_tws.py`) | `rest_client.py` |
| `indicator_engine.py` (→ `core/`) | `config.py` (→ Pydantic Settings) | `webapp.py` (replaced by API) |
| `exceptions.py` (extend) | `db_manager.py` (→ SQLAlchemy `db/`) | All utility scripts (separate repo/tools) |

---

## Non-Goals (For Now)
- **Multiple symbols per strategy** — keep 1:1 for simplicity, expand later
- **Backtesting integration** — separate service, not in SaaS MVP
- **Mobile app** — responsive web dashboard is sufficient
- **Social/copy trading** — future feature, architecture supports it via strategy templates
