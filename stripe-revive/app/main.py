# app/main.py (updated)
from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.config import settings
from app.webhooks import router as webhook_router
from app.database import init_db, get_db
from app.models import RecoveryEvent

app = FastAPI(title=settings.PROJECT_NAME)
templates = Jinja2Templates(directory="app/templates")

app.include_router(webhook_router)

@app.on_event("startup")
async def on_startup():
    await init_db()

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    # Real DB Queries
    # 1. Total Failed Revenue (Sum of amount_due where status='failed' or 'pending')
    result = await db.execute(select(func.sum(RecoveryEvent.amount_due)))
    failed_amount = result.scalar() or 0.0

    # 2. Recovered Revenue
    result_rec = await db.execute(select(func.sum(RecoveryEvent.amount_due)).where(RecoveryEvent.status == 'recovered'))
    recovered_amount = result_rec.scalar() or 0.0

    # 3. Active Dunning Count
    result_count = await db.execute(select(func.count(RecoveryEvent.id)).where(RecoveryEvent.status == 'pending'))
    active_count = result_count.scalar() or 0

    # 4. Recent Events
    result_events = await db.execute(select(RecoveryEvent).order_by(RecoveryEvent.created_at.desc()).limit(10))
    events = result_events.scalars().all()

    # View Model for Template
    event_list = []
    for e in events:
        event_list.append({
            "customer": e.stripe_customer_id,
            "amount": f"{e.amount_due:.2f}",
            "status": e.status.capitalize(),
            "date": e.created_at.strftime("%Y-%m-%d")
        })

    context = {
        "request": request,
        "failed_amount": f"{failed_amount:.2f}",
        "recovered_amount": f"{recovered_amount:.2f}",
        "active_count": active_count,
        "events": event_list
    }
    return templates.TemplateResponse("dashboard.html", context)
