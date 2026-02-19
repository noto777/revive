# AGENTS.md - IronHand SaaS Refactor Team

## Project
Refactor the IronHand monolithic trading bot into a multi-tenant SaaS application.

## Source Material
- **Live bot (READ-ONLY reference):** `G:\Projects\Personal\Core_Strategy_Live` on Rob-PC
- **SaaS repo (implementation target):** `G:\Projects\Personal\Dip_Strategy_SaaS` on Rob-PC
- **Analysis:** `/root/.openclaw/workspace-personal/ironhand/ANALYSIS.md`
- **Architecture:** `/root/.openclaw/workspace-personal/ironhand/ARCHITECTURE.md`

## ⚠️ Critical Rules
1. **NEVER modify anything in `Core_Strategy_Live`** — it is a live trading bot running real money
2. **SaaS uses Alpaca** as the broker, NOT IBKR. The live bot uses IBKR — we extract strategy logic only
3. **Validate each phase before advancing** — no skipping ahead
4. **All implementation goes into `Dip_Strategy_SaaS`** or the local workspace staging area

## Team Structure

### 🎯 Team Lead: Flounder (Opus)
- **Role:** Coordinator, reviewer, quality gate
- **Responsibilities:**
  - Assigns tasks to team members
  - Reviews deliverables before they're merged
  - Resolves conflicts between Architect and Implementer decisions
  - Reports progress to Rob
  - Final handoff to Edison for ongoing SaaS development

### 📐 Architect (Opus)
- **Role:** System designer
- **Responsibilities:**
  - Design module structure, database schema, API contracts
  - Define component boundaries and interfaces
  - Make technology decisions (frameworks, patterns)
  - Review Implementer's code for architectural compliance
- **Deliverables:** `ARCHITECTURE.md` ✅ (completed)

### 🔨 Implementer (Sonnet)
- **Role:** Code builder
- **Responsibilities:**
  - Build refactored modules following ARCHITECTURE.md exactly
  - Write clean, typed, documented Python code
  - Fix all critical issues from ANALYSIS.md
  - Do NOT make architectural decisions — escalate to Architect
- **Deliverables:** Refactored Python modules in staging area

### 🧪 Tester (Sonnet)
- **Role:** Quality assurance
- **Responsibilities:**
  - Write comprehensive test suite (pytest)
  - Unit tests for each module
  - Integration tests for component interactions
  - Verify all critical issues from ANALYSIS.md are resolved
  - Flag deviations from ARCHITECTURE.md
- **Deliverables:** Test suite + coverage report + issues doc

## Workflow

```
1. Architect designs → ARCHITECTURE.md ✅
2. Rob reviews architecture ← YOU ARE HERE
3. Team Lead assigns implementation tasks
4. Implementer builds modules (phase by phase)
5. Tester writes tests in parallel
6. Team Lead reviews implementation + tests
7. Iterate until all phases pass
8. Hand off to Edison for ongoing development
```

## Implementation Phases (from ARCHITECTURE.md)

### Phase 1: Clean & Consolidate
- Delete duplicate DB layer (sqlite_manager.py)
- Remove dead regime system
- Replace print() with structured logging
- Add graceful shutdown
- Extract main.py god-class into modules
- **Gate:** Runs identically to monolith on paper account

### Phase 2: Abstract & Isolate
- Create broker abstraction (Alpaca implementation for SaaS)
- Pydantic config models
- SQLAlchemy models + migration
- Internal event bus
- **Gate:** Same behavior, new structure

### Phase 3: API Layer
- FastAPI app with auth
- REST endpoints
- WebSocket dashboard
- Replace Flask webapp
- **Gate:** API-driven control of single strategy

### Phase 4: Multi-Tenant
- PostgreSQL migration
- Tenant isolation
- Multi-executor scheduler
- Encrypted credentials
- **Gate:** Two tenants running simultaneously, isolated

### Phase 5: Production Hardening
- Rate limiting, monitoring
- Docker/K8s deployment
- CI/CD pipeline
- **Gate:** Production-ready

## Communication Protocol
This is a **collaborative team**, not isolated sub-agents. All team members run as persistent sessions and can message each other directly.

### Session Labels
- `ironhand-lead` — Flounder (Team Lead)
- `ironhand-architect` — Architect
- `ironhand-impl` — Implementer
- `ironhand-tester` — Tester

### How to Reach Each Other
Use `sessions_send` with the target label:
```
sessions_send(label="ironhand-architect", message="Need clarification on broker interface...")
sessions_send(label="ironhand-impl", message="Architecture for Phase 2 is ready, here's what to build...")
sessions_send(label="ironhand-tester", message="Phase 1 implementation is done, ready for testing...")
sessions_send(label="ironhand-lead", message="Blocked on X, need Rob's input...")
```

### Communication Rules
- **Architect → Implementer:** Send design specs, answer questions, review code
- **Implementer → Architect:** Ask clarifying questions, propose alternatives
- **Implementer → Tester:** Notify when modules are ready for testing
- **Tester → Implementer:** Report test failures, flag issues
- **Tester → Architect:** Flag architectural deviations
- **Anyone → Team Lead:** Escalate blockers, report phase completion
- **Team Lead → Rob:** Progress updates, decisions that need human input
- **Don't spin wheels** — if blocked for more than one exchange, escalate to Team Lead
- **When in doubt, ask** — don't assume

## Tech Stack (SaaS)
- **Language:** Python 3.11+
- **Framework:** FastAPI
- **Database:** PostgreSQL + SQLAlchemy + Alembic
- **Broker:** Alpaca (alpaca-trade-api)
- **Auth:** JWT + API keys
- **Logging:** structlog
- **Testing:** pytest
- **Deployment:** Docker → Kubernetes
