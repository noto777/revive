#!/usr/bin/env python3
"""
Build verification script for IronHand SaaS.

Checks that all critical modules can be imported and basic functionality works.
Run after installing dependencies: pip install -r requirements.txt
"""

import sys
from pathlib import Path

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'


def test_import(module_name: str, description: str) -> bool:
    """Test if a module can be imported."""
    try:
        __import__(module_name)
        print(f"{GREEN}✓{RESET} {description}")
        return True
    except ImportError as e:
        print(f"{RED}✗{RESET} {description} - {e}")
        return False
    except Exception as e:
        print(f"{YELLOW}⚠{RESET} {description} - {e}")
        return False


def check_file_exists(filepath: str, description: str) -> bool:
    """Check if a file exists."""
    if Path(filepath).exists():
        print(f"{GREEN}✓{RESET} {description}")
        return True
    else:
        print(f"{RED}✗{RESET} {description} - File not found")
        return False


def main():
    print(f"\n{BOLD}IronHand SaaS - Build Verification{RESET}\n")
    print("=" * 60)
    
    results = []
    
    # File structure checks
    print(f"\n{BOLD}📁 File Structure{RESET}")
    results.append(check_file_exists("core/strategy_logic.py", "Core - Strategy Logic"))
    results.append(check_file_exists("core/core_manager.py", "Core - Exit Manager"))
    results.append(check_file_exists("core/indicators.py", "Core - Indicators"))
    results.append(check_file_exists("engine/executor.py", "Engine - Executor"))
    results.append(check_file_exists("engine/signals.py", "Engine - Signals"))
    results.append(check_file_exists("engine/events.py", "Engine - Event Bus"))
    results.append(check_file_exists("brokers/base.py", "Brokers - Base Interface"))
    results.append(check_file_exists("brokers/alpaca.py", "Brokers - Alpaca"))
    results.append(check_file_exists("brokers/paper.py", "Brokers - Paper"))
    results.append(check_file_exists("notifications/dispatcher.py", "Notifications - Dispatcher"))
    results.append(check_file_exists("db/models.py", "Database - Models"))
    results.append(check_file_exists("db/session.py", "Database - Session"))
    results.append(check_file_exists("api/app.py", "API - App Factory"))
    results.append(check_file_exists("pyproject.toml", "Config - pyproject.toml"))
    results.append(check_file_exists("alembic.ini", "Config - alembic.ini"))
    
    # Module import checks
    print(f"\n{BOLD}📦 Module Imports{RESET}")
    results.append(test_import("config", "Configuration"))
    results.append(test_import("logger", "Logging"))
    results.append(test_import("exceptions", "Exceptions"))
    results.append(test_import("core.strategy_logic", "Core - Strategy Logic"))
    results.append(test_import("core.core_manager", "Core - Exit Manager"))
    results.append(test_import("core.indicators", "Core - Indicators"))
    results.append(test_import("engine.signals", "Engine - Signals"))
    results.append(test_import("engine.events", "Engine - Event Bus"))
    results.append(test_import("engine.executor", "Engine - Executor"))
    results.append(test_import("brokers.base", "Brokers - Base"))
    results.append(test_import("brokers.alpaca", "Brokers - Alpaca"))
    results.append(test_import("brokers.paper", "Brokers - Paper"))
    results.append(test_import("notifications.base", "Notifications - Base"))
    results.append(test_import("notifications.telegram", "Notifications - Telegram"))
    results.append(test_import("notifications.webhook", "Notifications - Webhook"))
    results.append(test_import("notifications.dispatcher", "Notifications - Dispatcher"))
    results.append(test_import("db.models", "Database - Models"))
    results.append(test_import("db.session", "Database - Session"))
    
    # Try importing API (might fail if FastAPI not installed)
    print(f"\n{BOLD}🌐 API Components (requires dependencies){RESET}")
    results.append(test_import("api.app", "API - Application"))
    
    # Summary
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    total = len(results)
    passed = sum(results)
    failed = total - passed
    
    print(f"\n{BOLD}Summary:{RESET}")
    print(f"  Total checks: {total}")
    print(f"  {GREEN}Passed: {passed}{RESET}")
    if failed > 0:
        print(f"  {RED}Failed: {failed}{RESET}")
    
    if passed == total:
        print(f"\n{GREEN}{BOLD}✅ All checks passed!{RESET}")
        print(f"\n{BOLD}Next steps:{RESET}")
        print("  1. Install dependencies: pip install -e .")
        print("  2. Initialize database: alembic upgrade head")
        print("  3. Run API server: uvicorn api.app:app --reload")
        return 0
    else:
        print(f"\n{RED}{BOLD}❌ Some checks failed{RESET}")
        print(f"\n{BOLD}Troubleshooting:{RESET}")
        print("  - Install dependencies: pip install -r requirements.txt")
        print("  - Check Python version: python --version (need 3.11+)")
        print("  - Verify you're in the correct directory")
        return 1


if __name__ == "__main__":
    sys.exit(main())
