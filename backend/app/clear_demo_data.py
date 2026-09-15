"""
Remove the demo account and everything tied to it (campaigns, workflows,
contacts, events, drafts, integrations). Run this before connecting real
accounts and deploying, so no sample data ships alongside real data.

Usage (from the backend/ directory, with the venv active):
    python -m app.clear_demo_data
"""
from sqlalchemy import select

from .db import SessionLocal
from .models import User, Campaign, Workflow, Contact, Event, ContentDraft, Integration
from .seed_demo_data import DEMO_EMAIL


def clear():
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if not user:
            print(f"No demo account found ({DEMO_EMAIL}). Nothing to clear.")
            return

        for model in (Campaign, Workflow, Contact, Event, ContentDraft, Integration):
            rows = db.scalars(select(model).where(model.user_id == user.id)).all()
            for row in rows:
                db.delete(row)

        db.delete(user)
        db.commit()
        print(f"Demo account and all related data removed ({DEMO_EMAIL}).")
    finally:
        db.close()


if __name__ == "__main__":
    clear()


