"""
IronHand SaaS - Multi-Tenant Trading Strategy Platform

Refactored from monolithic live bot into clean, testable modules.

Phase 1 Complete:
✅ Project structure (6 packages)
✅ Unified database layer (SQLAlchemy, PostgreSQL-ready)
✅ Core strategy logic (pure business logic, no I/O)
✅ Regime system removed (flattened to configurable params)
✅ Structured logging (structlog, no print())
✅ Exception hierarchy (clean, typed)
✅ Pydantic Settings config (replaces globals)
✅ Graceful shutdown (signal handlers)
"""

__version__ = "0.1.0"
__author__ = "IronHand Team"
