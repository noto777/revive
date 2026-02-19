# app/webhooks.py
import stripe
from fastapi import APIRouter, Request, Header, HTTPException
from sqlalchemy import select
from app.config import settings
from app.scheduler import scheduler
from app.models import RecoveryEvent
from app.database import AsyncSessionLocal

router = APIRouter()
stripe.api_key = settings.STRIPE_API_KEY
stripe.api_version = settings.STRIPE_API_VERSION

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()

    # Signature verification (skip if using mock secret)
    if settings.STRIPE_WEBHOOK_SECRET and not settings.STRIPE_WEBHOOK_SECRET.startswith("whsec_mock"):
        try:
            event = stripe.Webhook.construct_event(
                payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
            )
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    else:
        import json
        event = json.loads(payload)

    async with AsyncSessionLocal() as db:
        if event['type'] == 'invoice.payment_failed':
            invoice = event['data']['object']
            customer_id = invoice.get('customer')
            amount = (invoice.get('amount_due') or 0) / 100.0
            customer_email = invoice.get('customer_email') or "customer@example.com"
            invoice_id = invoice.get('id')

            print(f"💰 PAYMENT FAILED: Customer {customer_id} owes ${amount:.2f}")

            # Save to DB
            new_event = RecoveryEvent(
                stripe_customer_id=customer_id,
                invoice_id=invoice_id,
                amount_due=amount,
                status='pending'
            )
            db.add(new_event)
            await db.commit()

            # Fire dunning sequence
            await scheduler.schedule_dunning_sequence(customer_id, customer_email, amount)

        elif event['type'] == 'invoice.payment_succeeded':
            invoice = event['data']['object']
            customer_id = invoice.get('customer')
            invoice_id = invoice.get('id')

            print(f"✅ PAYMENT RECOVERED: Customer {customer_id}")

            # Mark matching pending events as recovered
            result = await db.execute(
                select(RecoveryEvent).where(
                    RecoveryEvent.stripe_customer_id == customer_id,
                    RecoveryEvent.status == 'pending'
                )
            )
            events = result.scalars().all()
            for ev in events:
                ev.status = 'recovered'
            await db.commit()
            print(f"✅ Marked {len(events)} event(s) as recovered for {customer_id}")

    return {"status": "success"}
