# FlowPilot AI — Final Local Build

A server-backed marketing automation dashboard with a clean SaaS UI, database persistence, CRUD pages, analytics, content drafts, workflows, contacts, and optional live Google/Shopify integrations.

## Easiest way to run (Windows)

**You do not need to type terminal commands.**

1. Install **Python 3.11+** once if it is not already installed.
2. Extract this ZIP.
3. Double-click **`START_FLOWPILOT.bat`**.
4. The launcher creates its own virtual environment, installs the libraries, creates a local `.env`, starts the server, and opens the website.
5. Create an account inside FlowPilot and use the dashboard.

On later launches, just double-click `START_FLOWPILOT.bat` again.

## What is included

- Dashboard with database-backed metrics and recent activity
- Campaign CRUD and campaign metric editing
- Audience/contact management and search
- Workflow creation, activation/deactivation and deletion
- Content Studio with saved drafts
- Local fallback content generation when an OpenAI key is not configured
- Insights and Reports from stored data
- Settings stored in the database
- Integration status pages
- Optional live Google OAuth, GA4 and Google Ads sync
- Optional live Shopify OAuth and order/customer sync
- SQLite database for zero-configuration local development
- PostgreSQL-ready configuration
- No fabricated marketing metrics
- Automatic real timestamps
- Responsive dashboard UI

## Optional real integrations

The core application works without provider credentials. Google, Shopify and AI features that call external services require credentials belonging to the account/project you connect. These credentials are intentionally not included in the ZIP.

Add optional variables to `backend/.env` only when you need them. Never put secrets into `frontend/index.html`.

## Database

Local data is stored in `backend/flowpilot.db`. It is created automatically on first launch. Deleting that file resets the local workspace database.

## Demo data (for local exploring/testing only)

By design, FlowPilot never invents numbers inside the running app — a fresh account shows a genuinely empty dashboard until you add campaigns/contacts or connect real integrations. To explore the UI with something in it, seed a separate demo account:

```
cd backend
.venv/bin/python -m app.seed_demo_data      # Windows: .venv\Scripts\python.exe -m app.seed_demo_data
```

This creates one login (`demo@flowpilot.ai` / `Demo12345!`) with sample campaigns, contacts, workflows, events, and content drafts. It does not touch any other account and does not change how the API behaves — the demo numbers are just ordinary rows in the database.

When you're ready to move to real data and deploy, remove the demo account cleanly:

```
cd backend
.venv/bin/python -m app.clear_demo_data     # Windows: .venv\Scripts\python.exe -m app.clear_demo_data
```

Then register your real account, connect Google/Shopify from the Integrations page with your own credentials, and the dashboard will fill in from actual activity.

## Deploying (Render)

This repo includes a `Dockerfile` and a `render.yaml` Blueprint, so Render can build and host the app plus a managed Postgres database with one click.

1. **Push this folder to a GitHub repo** (Render deploys from a repo, not a local zip):
   ```
   cd flowpilot-real
   git init
   git add .
   git commit -m "Initial commit"
   ```
   Create an empty repo at https://github.com/new, then:
   ```
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git branch -M main
   git push -u origin main
   ```
2. Go to https://dashboard.render.com, sign in, click **New > Blueprint**, and pick this GitHub repo. Render reads `render.yaml` and provisions both the web service and a free Postgres database automatically. `SECRET_KEY` and `ENCRYPTION_KEY` are generated for you.
3. Once it's deployed, copy the live URL Render shows you (`https://your-app.onrender.com`), then in the service's **Environment** tab set `FRONTEND_URL` to that exact URL and save — Render will redeploy automatically.
4. Open the live URL and register your real account. To see it with sample data instead (or in addition), use the env-var-triggered seed described below — Render's free web service plan does not include shell/SSH access, so the local `python -m app.seed_demo_data` command won't work there directly.
5. To connect real Google/Shopify integrations in production, add `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/`SHOPIFY_CLIENT_ID`/`SHOPIFY_CLIENT_SECRET` as environment variables, and update each provider's OAuth app settings to use your live `https://your-app.onrender.com/api/integrations/.../callback` redirect URIs instead of `127.0.0.1`.

### Seeding/clearing demo data without shell access

On platforms like Render's free plan where there's no shell, set an environment variable on the service instead:

- Add `SEED_DEMO_DATA=true` in the Environment tab and save. Render redeploys, and the app seeds the demo account (`demo@flowpilot.ai` / `Demo12345!`) once on startup — check the deploy logs for a "Demo data created." line.
- When you're ready to remove it, set `CLEAR_DEMO_DATA=true` instead (and remove `SEED_DEMO_DATA`) and save. On the next boot it wipes the demo account.
- After either one runs, set the variable back to blank/false so it doesn't repeat on every future restart (harmless either way since both are idempotent, but cleaner).

**Worth knowing:** Render's free Postgres database expires 30 days after creation and is deleted — fine for testing, but before that window closes you'll want to upgrade it to a paid plan (starts around $6-7/month) from the Render dashboard so your real data isn't lost. The free web service also spins down after 15 minutes of inactivity and takes a few seconds to wake back up on the next request; upgrading the web service to a paid instance removes that cold start.

## API

When the server is running:
- App: http://127.0.0.1:8000/
- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/api/health

## Important truthfulness rule

FlowPilot does not invent campaign performance, open rates, conversions, revenue, ROI, or provider data. If real data does not exist, the UI leaves the metric blank or shows an empty state.
