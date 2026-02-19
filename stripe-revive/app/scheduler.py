# app/scheduler.py
import asyncio
from datetime import datetime, timedelta
from app.email import send_email

# Mock in-memory queue for MVP
# In prod, this would be Redis/RQ
class MockScheduler:
    async def schedule_dunning_sequence(self, customer_id: str, email: str, amount: float):
        print(f"⏰ Scheduling Dunning Sequence for {customer_id}")
        
        # Day 0 (Immediate)
        await send_email(
            to_email=email,
            subject="Action Required: Payment Failed",
            template_name="payment_failed_day0",
            context={"amount": amount, "link": "https://stripe.com/pay/..."}
        )
        
        # Day 3 (Mocked as immediate for test)
        # In prod: enqueue_at(datetime.now() + timedelta(days=3), ...)
        print(f"🗓️ Scheduled: Day 3 Reminder for {email}")
        
        # Day 7
        print(f"🗓️ Scheduled: Day 7 Final Notice for {email}")

scheduler = MockScheduler()
