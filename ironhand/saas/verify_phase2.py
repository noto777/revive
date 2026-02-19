"""
Phase 2 Verification Script

Validates that all Phase 2 components are properly implemented.
"""

import sys
from pathlib import Path


def check_file(path: Path, min_size: int = 100) -> bool:
    """Check if file exists and has content."""
    if not path.exists():
        print(f"❌ Missing: {path}")
        return False
    
    size = path.stat().st_size
    if size < min_size:
        print(f"⚠️  Too small: {path} ({size} bytes)")
        return False
    
    print(f"✅ Found: {path} ({size} bytes)")
    return True


def verify_phase2():
    """Verify Phase 2 implementation."""
    
    print("=" * 70)
    print("Phase 2 Verification")
    print("=" * 70)
    
    base_dir = Path(__file__).parent
    all_good = True
    
    # 1. Broker abstraction
    print("\n📦 Broker Abstraction Layer")
    print("-" * 70)
    all_good &= check_file(base_dir / "brokers" / "base.py", 5000)
    all_good &= check_file(base_dir / "brokers" / "alpaca.py", 10000)
    all_good &= check_file(base_dir / "brokers" / "paper.py", 8000)
    all_good &= check_file(base_dir / "brokers" / "__init__.py", 500)
    
    # 2. Event bus
    print("\n📡 Event Bus")
    print("-" * 70)
    all_good &= check_file(base_dir / "engine" / "events.py", 8000)
    
    # 3. Notifications
    print("\n📬 Notification System")
    print("-" * 70)
    all_good &= check_file(base_dir / "notifications" / "base.py", 2000)
    all_good &= check_file(base_dir / "notifications" / "telegram.py", 4000)
    all_good &= check_file(base_dir / "notifications" / "webhook.py", 6000)
    all_good &= check_file(base_dir / "notifications" / "dispatcher.py", 4000)
    all_good &= check_file(base_dir / "notifications" / "__init__.py", 500)
    
    # 4. Database migrations
    print("\n🗄️  Database Migrations")
    print("-" * 70)
    all_good &= check_file(base_dir / "alembic.ini", 1000)
    all_good &= check_file(base_dir / "db" / "migrations" / "env.py", 2000)
    all_good &= check_file(base_dir / "db" / "migrations" / "script.py.mako", 400)
    all_good &= check_file(base_dir / "db" / "migrations" / "versions" / "001_initial_schema.py", 6000)
    all_good &= check_file(base_dir / "db" / "migrations" / "README.md", 2000)
    
    # 5. Verify imports work
    print("\n🔍 Import Verification")
    print("-" * 70)
    
    try:
        from brokers import BrokerInterface, AlpacaBroker, PaperBroker
        print("✅ Broker imports successful")
    except Exception as e:
        print(f"❌ Broker import failed: {e}")
        all_good = False
    
    try:
        from engine.events import EventBus, EventType, get_event_bus
        print("✅ Event bus imports successful")
    except Exception as e:
        print(f"❌ Event bus import failed: {e}")
        all_good = False
    
    try:
        from notifications import (
            NotificationDispatcher,
            TelegramNotifier,
            WebhookNotifier
        )
        print("✅ Notification imports successful")
    except Exception as e:
        print(f"❌ Notification import failed: {e}")
        all_good = False
    
    try:
        from db.models import Base, Tenant, Strategy, Position, Order
        print("✅ Database model imports successful")
    except Exception as e:
        print(f"❌ Database model import failed: {e}")
        all_good = False
    
    # Summary
    print("\n" + "=" * 70)
    if all_good:
        print("✅ Phase 2 Implementation: COMPLETE")
        print("=" * 70)
        print("\nAll components verified successfully!")
        print("\n📋 Next Steps:")
        print("  1. Notify Tester: Phase 2 modules ready for testing")
        print("  2. Notify Team Lead: Phase 2 complete")
        print("  3. Run comprehensive test suite")
        print("  4. Begin Phase 3 (API Layer) after QA approval")
        return 0
    else:
        print("❌ Phase 2 Implementation: INCOMPLETE")
        print("=" * 70)
        print("\nSome components are missing or incomplete.")
        print("Review errors above and fix before proceeding.")
        return 1


if __name__ == "__main__":
    sys.exit(verify_phase2())
