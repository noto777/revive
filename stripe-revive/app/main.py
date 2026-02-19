# app/main.py
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from app.config import settings
from app.webhooks import router as webhook_router
from app.database import init_db, get_db
from app.models import RecoveryEvent
import json, os, secrets

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title=settings.PROJECT_NAME)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

templates = Jinja2Templates(directory="app/templates")
security = HTTPBasic()

app.include_router(webhook_router)

@app.on_event("startup")
async def on_startup():
    await init_db()

# ── Dashboard Auth ──────────────────────────────────────────────
def verify_dashboard(credentials: HTTPBasicCredentials = Depends(security)):
    try:
        correct_user = secrets.compare_digest(
            credentials.username.encode("utf8"),
            settings.DASHBOARD_USER.encode("utf8")
        )
        correct_pass = secrets.compare_digest(
            credentials.password.encode("utf8"),
            settings.DASHBOARD_PASS.encode("utf8")
        )
    except Exception:
        correct_user = correct_pass = False

    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": 'Basic realm="Revive Dashboard"'},
        )
    return credentials.username

# ── Landing Page (public) ───────────────────────────────────────
@app.get("/landing", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})

# ── Waitlist (rate limited) ─────────────────────────────────────
class WaitlistEntry(BaseModel):
    email: str

@app.post("/waitlist")
@limiter.limit("3/minute")
async def waitlist(request: Request, entry: WaitlistEntry):
    if not entry.email or "@" not in entry.email:
        raise HTTPException(status_code=400, detail="Invalid email")
    path = "waitlist.json"
    emails = []
    if os.path.exists(path):
        with open(path) as f:
            emails = json.load(f)
    if entry.email not in emails:
        emails.append(entry.email)
        with open(path, "w") as f:
            json.dump(emails, f, indent=2)
        print(f"🎉 Waitlist signup: {entry.email} (total: {len(emails)})")
    return {"status": "ok", "count": len(emails)}

# ── Dashboard (protected) ───────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(verify_dashboard)
):
    result = await db.execute(select(func.sum(RecoveryEvent.amount_due)))
    failed_amount = result.scalar() or 0.0

    result_rec = await db.execute(
        select(func.sum(RecoveryEvent.amount_due)).where(RecoveryEvent.status == 'recovered')
    )
    recovered_amount = result_rec.scalar() or 0.0

    result_count = await db.execute(
        select(func.count(RecoveryEvent.id)).where(RecoveryEvent.status == 'pending')
    )
    active_count = result_count.scalar() or 0

    result_events = await db.execute(
        select(RecoveryEvent).order_by(RecoveryEvent.created_at.desc()).limit(10)
    )
    events = result_events.scalars().all()

    event_list = [{
        "customer": e.stripe_customer_id,
        "amount": f"{e.amount_due:.2f}",
        "status": e.status.capitalize(),
        "date": e.created_at.strftime("%Y-%m-%d")
    } for e in events]

    # Waitlist count
    waitlist_count = 0
    if os.path.exists("waitlist.json"):
        with open("waitlist.json") as f:
            waitlist_count = len(json.load(f))

    context = {
        "request": request,
        "failed_amount": f"{failed_amount:.2f}",
        "recovered_amount": f"{recovered_amount:.2f}",
        "active_count": active_count,
        "events": event_list,
        "waitlist_count": waitlist_count,
    }
    return templates.TemplateResponse("dashboard.html", context)

# ── Waitlist admin view (protected) ────────────────────────────
@app.get("/admin/waitlist")
async def view_waitlist(username: str = Depends(verify_dashboard)):
    if os.path.exists("waitlist.json"):
        with open("waitlist.json") as f:
            emails = json.load(f)
        return {"count": len(emails), "emails": emails}
    return {"count": 0, "emails": []}
