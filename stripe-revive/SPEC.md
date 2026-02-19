# Stripe Churn Recovery (Project "Revive") - MVP Spec

## 🎯 Goal
Build a "set and forget" SaaS that recovers failed Stripe payments for other SaaS founders.
**Value Prop:** "We recover 15% of your lost revenue automatically."

## 🛠 Tech Stack (Speed Stack)
*   **Backend:** Python (FastAPI) - Async is good for webhooks.
*   **Database:** PostgreSQL (User data, Recovery logs).
*   **Queue:** Redis/RQ (For scheduling emails).
*   **Billing:** Stripe Connect (Platform model).
*   **Frontend:** Tailwind + Jinja2 (Keep it server-side rendered for speed) OR React if complex. *Decision: Server-side (FastAPI + Jinja) is faster for MVP.*

## 📦 MVP Scope (7 Days)

### 1. The Core Loop (Dunning)
1.  **Ingest:** Listen for Stripe Webhook `invoice.payment_failed`.
2.  **Analyze:** Check if retriable.
3.  **Schedule:**
    *   Day 0: "Payment Failed" email (Generic/Friendly).
    *   Day 3: "Subscription at Risk" email.
    *   Day 7: "Final Notice" email.
4.  **Recover:** Listen for `invoice.payment_succeeded` -> Cancel future emails -> **Log $$$ Saved.**

### 2. User Dashboard
*   **Connect:** "Connect with Stripe" button (OAuth).
*   **Stats:**
    *   Total Failed Revenue (Last 30d).
    *   Total Recovered Revenue (Last 30d).
    *   Recovery Rate %.
*   **Settings:** Customize Brand Name / Logo for emails.

### 3. Pricing (How we make money)
*   **MVP Model:** Flat $49/mo (Simpler to build than taking a % cut for now).
*   **Integration:** We use Stripe Billing for *our* subscription.

## 📅 Build Phases

### Phase 1: Plumbing (Days 1-2)
*   [ ] FastAPI Repo Setup
*   [ ] PostgreSQL Schema (Users, Events, Recoveries)
*   [ ] Stripe Connect OAuth Flow

### Phase 2: The Engine (Days 3-4)
*   [ ] Webhook Handler (`invoice.payment_failed`)
*   [ ] Email Scheduler (Redis)
*   [ ] Email Templates (Jinja2)

### Phase 3: The Face (Days 5-6)
*   [ ] Dashboard UI (Tailwind)
*   [ ] Settings Page

### Phase 4: Launch (Day 7)
*   [ ] Deploy (Render/Railway/DigitalOcean)
*   [ ] Post on Reddit/Twitter

## 🚦 Immediate Next Steps
1.  Set up FastAPI Boilerplate.
2.  Define DB Schema.
