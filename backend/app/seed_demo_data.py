"""
Populate FlowPilot with a demo account full of realistic sample data.

This is for exploring/testing the UI locally. It writes clearly-labelled
demo rows tied to one demo login — it does not touch any other account,
and it does not fabricate anything inside the running app itself (the
API/dashboard logic is unchanged and still never invents numbers on its
own). Run this once, look around, then run clear_demo_data.py before you
connect real integrations and deploy.

Usage (from the backend/ directory, with the venv active):
    python -m app.seed_demo_data
"""
import random
from datetime import datetime, timedelta, timezone

from .db import Base, engine, SessionLocal
from .models import User, Campaign, Workflow, Contact, Event, ContentDraft
from .security import hash_password
from sqlalchemy import select

DEMO_EMAIL = "demo@flowpilot.ai"
DEMO_PASSWORD = "Demo12345!"
DEMO_NAME = "Demo Account"

random.seed(42)
NOW = datetime.now(timezone.utc)


def days_ago(d, hour=None):
    t = NOW - timedelta(days=d)
    if hour is not None:
        t = t.replace(hour=hour, minute=random.randint(0, 59))
    return t


FIRST_NAMES = ["Ava", "Liam", "Noah", "Maya", "Ethan", "Zoe", "Priya", "Arjun", "Sofia", "Lucas",
               "Grace", "Omar", "Ines", "Kenji", "Chloe", "Mateo", "Nina", "Ravi", "Elena", "Jack",
               "Ana", "Sam", "Yuki", "Leo", "Isla", "Diego", "Amara", "Tom", "Lily", "Hassan"]
LAST_NAMES = ["Patel", "Garcia", "Kim", "Novak", "Rossi", "Chen", "Okafor", "Muller", "Silva", "Ito",
              "Nguyen", "Andersen", "Haddad", "Reyes", "Kowalski", "Fischer", "Costa", "Tanaka", "Lopez", "Brown"]
SOURCES = ["Manual", "Website", "Shopify", "Import"]


def seed():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if existing:
            print(f"Demo account already exists ({DEMO_EMAIL}). Run clear_demo_data.py first if you want to reseed.")
            return

        user = User(name=DEMO_NAME, email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD))
        db.add(user)
        db.commit()
        db.refresh(user)

        # ---- Campaigns ----
        campaigns_data = [
            dict(name="Spring Sale Blast", channel="Email", status="Active", audience="All contacts",
                 budget=500, impressions=42000, clicks=3100, conversions=210, spend=480, revenue=8900),
            dict(name="Google Search - Brand", channel="Google Ads", status="Active", audience="New visitors",
                 budget=1200, impressions=88000, clicks=4200, conversions=180, spend=1150, revenue=15400),
            dict(name="Retarget Cart Abandoners", channel="Email", status="Active", audience="Cart abandoners",
                 budget=150, impressions=12000, clicks=1800, conversions=140, spend=140, revenue=5200),
            dict(name="Instagram Reels Launch", channel="Instagram", status="Paused", audience="18-34 lookalike",
                 budget=800, impressions=65000, clicks=2900, conversions=95, spend=760, revenue=4100),
            dict(name="LinkedIn B2B Outreach", channel="LinkedIn", status="Active", audience="B2B decision makers",
                 budget=600, impressions=15000, clicks=620, conversions=34, spend=590, revenue=9800),
            dict(name="Holiday Email Series", channel="Email", status="Completed", audience="All contacts",
                 budget=300, impressions=30000, clicks=2600, conversions=310, spend=295, revenue=11200),
            dict(name="New Product Teaser", channel="Facebook Ads", status="Draft", audience="All contacts",
                 budget=0, impressions=0, clicks=0, conversions=0, spend=0, revenue=0),
            dict(name="Referral Program Push", channel="Email", status="Active", audience="Existing customers",
                 budget=100, impressions=8000, clicks=900, conversions=60, spend=95, revenue=2600),
        ]
        campaigns = []
        for c in campaigns_data:
            camp = Campaign(user_id=user.id, created_at=days_ago(random.randint(20, 60)), **c)
            db.add(camp)
            campaigns.append(camp)
        db.commit()
        for c in campaigns:
            db.refresh(c)

        # ---- Workflows ----
        workflows_data = [
            dict(name="Welcome Series", trigger="Contact added",
                 actions=["Send welcome email", "Wait 2 days", "Send tips email"], active=True),
            dict(name="Cart Abandonment", trigger="Cart abandoned",
                 actions=["Wait 1 hour", "Send reminder email", "Wait 1 day", "Send discount email"], active=True),
            dict(name="Re-engagement", trigger="No activity 30 days",
                 actions=["Send re-engagement email"], active=False),
            dict(name="Post-purchase Upsell", trigger="Order placed",
                 actions=["Wait 3 days", "Send upsell email"], active=True),
            dict(name="Lead Scoring Alert", trigger="Form submitted",
                 actions=["Notify sales team"], active=False),
        ]
        for w in workflows_data:
            db.add(Workflow(user_id=user.id, created_at=days_ago(random.randint(10, 50)), **w))
        db.commit()

        # ---- Contacts ----
        used_emails = set()
        contacts = []
        for _ in range(36):
            first, last = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
            email = f"{first.lower()}.{last.lower()}{random.randint(1,999)}@example.com"
            if email in used_emails:
                continue
            used_emails.add(email)
            status = random.choices(["Active", "Unsubscribed"], weights=[0.88, 0.12])[0]
            contact = Contact(user_id=user.id, name=f"{first} {last}", email=email,
                               source=random.choice(SOURCES), status=status,
                               created_at=days_ago(random.randint(1, 90)))
            db.add(contact)
            contacts.append(contact)
        db.commit()

        # ---- Events (drives dashboard open/conversion rates + recent activity) ----
        email_campaigns = [c for c in campaigns if c.channel == "Email"]
        other_campaigns = [c for c in campaigns if c.channel != "Email" and c.status != "Draft"]

        for _ in range(480):
            d = random.randint(0, 45)
            camp = random.choice(email_campaigns) if email_campaigns else None
            db.add(Event(user_id=user.id, campaign_id=camp.id if camp else None,
                          event_type="email_sent", channel="Email", value=0,
                          occurred_at=days_ago(d, hour=random.randint(6, 20))))
        for _ in range(310):
            d = random.randint(0, 45)
            camp = random.choice(email_campaigns) if email_campaigns else None
            db.add(Event(user_id=user.id, campaign_id=camp.id if camp else None,
                          event_type="email_open", channel="Email", value=0,
                          occurred_at=days_ago(d, hour=random.randint(6, 22))))
        for _ in range(95):
            d = random.randint(0, 45)
            camp = random.choice(campaigns)
            db.add(Event(user_id=user.id, campaign_id=camp.id,
                          event_type="conversion", channel=camp.channel, value=round(random.uniform(20, 220), 2),
                          occurred_at=days_ago(d, hour=random.randint(8, 21))))
        for camp in other_campaigns + email_campaigns:
            if camp.revenue <= 0:
                continue
            chunks = random.randint(3, 8)
            for i in range(chunks):
                db.add(Event(user_id=user.id, campaign_id=camp.id,
                              event_type="revenue", channel=camp.channel,
                              value=round(camp.revenue / chunks, 2),
                              occurred_at=days_ago(random.randint(0, 40), hour=random.randint(8, 20))))
        db.commit()

        # ---- Content drafts ----
        drafts = [
            dict(title="Spring Sale Announcement", channel="Email",
                 body="Subject: Spring is here — 20% off everything\n\nHi there,\n\nOur biggest spring sale starts today. Use code SPRING20 at checkout.\n\nShop now and save.\n\n— The Team"),
            dict(title="Cart Reminder", channel="Email",
                 body="Subject: You left something behind\n\nHi,\n\nYour cart is waiting. Complete your order in the next 24 hours and get free shipping.\n\nComplete my order"),
            dict(title="Product Launch Teaser", channel="Instagram",
                 body="Something new is coming. 👀\n\nWe've been working on this for months — get ready.\n\n#ComingSoon #NewLaunch"),
            dict(title="B2B Case Study Share", channel="LinkedIn",
                 body="How one of our customers cut onboarding time by 40% using automated workflows.\n\nRead the full case study on our blog — link in comments."),
        ]
        for d in drafts:
            db.add(ContentDraft(user_id=user.id, created_at=days_ago(random.randint(1, 30)), **d))
        db.commit()

        print("Demo data created.")
        print(f"  Login email:    {DEMO_EMAIL}")
        print(f"  Login password: {DEMO_PASSWORD}")
        print(f"  Campaigns: {len(campaigns)}  Contacts: {len(contacts)}  Workflows: {len(workflows_data)}  Drafts: {len(drafts)}")
        print("Integrations (Google/Shopify/etc.) are left disconnected — connect your real accounts")
        print("from the Integrations page when you're ready.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
