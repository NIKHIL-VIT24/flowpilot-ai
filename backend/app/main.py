from datetime import datetime, timezone, timedelta
from collections import Counter
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
import secrets, urllib.parse, httpx
import jwt
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_
from .config import settings
from .db import Base, engine, get_db
from .models import User, Campaign, Workflow, Contact, Event, Integration, ContentDraft
from .schemas import *
from .security import hash_password, verify_password, create_token, current_user
from .services import encrypt_config, decrypt_config, generate_ai
from pathlib import Path

Base.metadata.create_all(engine)
app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_url, "http://localhost:8000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

ROOT = Path(__file__).resolve().parents[2]
FRONT = ROOT / "frontend"

@app.get("/api/health")
def health(): return {"ok": True, "time": datetime.now(timezone.utc)}

@app.post("/api/auth/register")
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email=data.email.lower()
    if db.scalar(select(User).where(User.email==email)): raise HTTPException(409,"Email already registered")
    user=User(name=data.name.strip(), email=email, password_hash=hash_password(data.password))
    db.add(user); db.commit(); db.refresh(user)
    return {"access_token":create_token(user.id),"user":UserOut.model_validate(user)}

@app.post("/api/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user=db.scalar(select(User).where(User.email==data.email.lower()))
    if not user or not verify_password(data.password,user.password_hash): raise HTTPException(401,"Invalid email or password")
    return {"access_token":create_token(user.id),"user":UserOut.model_validate(user)}

@app.get("/api/auth/me", response_model=UserOut)
def me(user=Depends(current_user)): return user

@app.post("/api/auth/logout")
def logout(): return {"ok":True}

def user_campaigns(db,user_id): return db.scalars(select(Campaign).where(Campaign.user_id==user_id).order_by(Campaign.created_at.desc())).all()

@app.get("/api/dashboard")
def dashboard(db:Session=Depends(get_db), user=Depends(current_user)):
    camps=user_campaigns(db,user.id)
    contacts=db.scalar(select(func.count(Contact.id)).where(Contact.user_id==user.id)) or 0
    workflows=db.scalar(select(func.count(Workflow.id)).where(Workflow.user_id==user.id,Workflow.active==True)) or 0
    opens=db.scalar(select(func.count(Event.id)).where(Event.user_id==user.id,Event.event_type=="email_open")) or 0
    sends=db.scalar(select(func.count(Event.id)).where(Event.user_id==user.id,Event.event_type=="email_sent")) or 0
    conv=db.scalar(select(func.count(Event.id)).where(Event.user_id==user.id,Event.event_type=="conversion")) or 0
    opens_rate=round(opens/sends*100,2) if sends else None
    conversion_rate=round(conv/sends*100,2) if sends else None
    # Prefer event-level conversion data when available; otherwise use stored
    # campaign conversion totals (for example, data imported from Google Ads).
    conversion_events=db.scalars(select(Event).where(Event.user_id==user.id, Event.event_type=="conversion")).all()
    channels=Counter(e.channel or "Unknown" for e in conversion_events)
    if not channels:
        for c in camps:
            if c.conversions:
                channels[c.channel]+=c.conversions

    events=db.scalars(
        select(Event).where(Event.user_id==user.id).order_by(Event.occurred_at.desc()).limit(8)
    ).all()
    recent_events=[{
        "id":e.id, "event_type":e.event_type, "channel":e.channel,
        "value":e.value, "campaign_id":e.campaign_id,
        "occurred_at":e.occurred_at.isoformat()
    } for e in events]
    recent=[CampaignOut.model_validate(c).model_dump(mode="json") for c in camps[:8]]
    return {"contacts":contacts,"open_rate":opens_rate,"conversion_rate":conversion_rate,
            "active_automations":workflows,"channels":dict(channels),"campaigns":recent,
            "recent_events":recent_events,"data_available":bool(camps or contacts or sends)}

@app.get("/api/campaigns",response_model=list[CampaignOut])
def campaigns(db:Session=Depends(get_db), user=Depends(current_user)):
    return user_campaigns(db,user.id)

@app.post("/api/campaigns",response_model=CampaignOut)
def create_campaign(data:CampaignIn,db:Session=Depends(get_db),user=Depends(current_user)):
    c=Campaign(user_id=user.id,**data.model_dump()); db.add(c); db.commit(); db.refresh(c); return c

@app.patch("/api/campaigns/{cid}",response_model=CampaignOut)
def update_campaign(cid:int,data:CampaignUpdate,db:Session=Depends(get_db),user=Depends(current_user)):
    c=db.scalar(select(Campaign).where(Campaign.id==cid,Campaign.user_id==user.id))
    if not c: raise HTTPException(404,"Campaign not found")
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(c,k,v)
    db.commit(); db.refresh(c); return c

@app.delete("/api/campaigns/{cid}")
def delete_campaign(cid:int,db:Session=Depends(get_db),user=Depends(current_user)):
    c=db.scalar(select(Campaign).where(Campaign.id==cid,Campaign.user_id==user.id))
    if not c: raise HTTPException(404,"Campaign not found")
    db.delete(c); db.commit(); return {"ok":True}

@app.get("/api/workflows",response_model=list[WorkflowOut])
def workflows(db:Session=Depends(get_db),user=Depends(current_user)):
    return db.scalars(select(Workflow).where(Workflow.user_id==user.id).order_by(Workflow.created_at.desc())).all()

@app.post("/api/workflows",response_model=WorkflowOut)
def create_workflow(data:WorkflowIn,db:Session=Depends(get_db),user=Depends(current_user)):
    w=Workflow(user_id=user.id,**data.model_dump()); db.add(w); db.commit(); db.refresh(w); return w

@app.patch("/api/workflows/{wid}",response_model=WorkflowOut)
def update_workflow(wid:int,data:WorkflowUpdate,db:Session=Depends(get_db),user=Depends(current_user)):
    w=db.scalar(select(Workflow).where(Workflow.id==wid,Workflow.user_id==user.id))
    if not w: raise HTTPException(404,"Workflow not found")
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(w,k,v)
    db.commit(); db.refresh(w); return w

@app.delete("/api/workflows/{wid}")
def delete_workflow(wid:int,db:Session=Depends(get_db),user=Depends(current_user)):
    w=db.scalar(select(Workflow).where(Workflow.id==wid,Workflow.user_id==user.id))
    if not w: raise HTTPException(404,"Workflow not found")
    db.delete(w); db.commit(); return {"ok":True}

@app.get("/api/contacts",response_model=list[ContactOut])
def contacts(search:str|None=None,db:Session=Depends(get_db),user=Depends(current_user)):
    q=select(Contact).where(Contact.user_id==user.id)
    if search: q=q.where(or_(Contact.name.ilike(f"%{search}%"),Contact.email.ilike(f"%{search}%")))
    return db.scalars(q.order_by(Contact.created_at.desc())).all()

@app.post("/api/contacts",response_model=ContactOut)
def create_contact(data:ContactIn,db:Session=Depends(get_db),user=Depends(current_user)):
    c=Contact(user_id=user.id,**data.model_dump()); db.add(c); db.commit(); db.refresh(c); return c

@app.delete("/api/contacts/{cid}")
def delete_contact(cid:int,db:Session=Depends(get_db),user=Depends(current_user)):
    c=db.scalar(select(Contact).where(Contact.id==cid,Contact.user_id==user.id))
    if not c: raise HTTPException(404,"Contact not found")
    db.delete(c); db.commit(); return {"ok":True}

@app.post("/api/events")
def ingest_event(event_type:str,channel:str|None=None,value:float=0,campaign_id:int|None=None,db:Session=Depends(get_db),user=Depends(current_user)):
    e=Event(user_id=user.id,event_type=event_type,channel=channel,value=value,campaign_id=campaign_id); db.add(e); db.commit(); return {"ok":True}

@app.get("/api/analytics")
def analytics(start:str|None=None,end:str|None=None,db:Session=Depends(get_db),user=Depends(current_user)):
    q=select(Event).where(Event.user_id==user.id)
    if start:
        q=q.where(Event.occurred_at>=datetime.fromisoformat(start).replace(tzinfo=timezone.utc))
    if end:
        q=q.where(Event.occurred_at<=datetime.fromisoformat(end).replace(tzinfo=timezone.utc))
    events=db.scalars(q).all(); counts=Counter(e.event_type for e in events); channels=Counter(e.channel for e in events if e.channel)
    revenue=sum(e.value for e in events if e.event_type=="revenue")
    return {"events":counts,"channels":channels,"revenue":revenue,"total_events":len(events)}

@app.get("/api/reports")
def reports(db:Session=Depends(get_db),user=Depends(current_user)):
    camps=user_campaigns(db,user.id)
    rows=[]
    for c in camps:
        ctr=round(c.clicks/c.impressions*100,2) if c.impressions else None
        roi=round((c.revenue-c.spend)/c.spend*100,2) if c.spend else None
        rows.append({"id":c.id,"name":c.name,"channel":c.channel,"impressions":c.impressions,"clicks":c.clicks,"ctr":ctr,"conversions":c.conversions,"spend":c.spend,"revenue":c.revenue,"roi":roi})
    return rows


# ---------- Real provider OAuth + synchronization ----------
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/adwords",
]

def _oauth_state(user_id:int, provider:str):
    # Signed state prevents a callback from being attached to another workspace.
    return create_token(user_id) + "." + provider

def _parse_state(state:str):
    token, provider = state.rsplit(".", 1)
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    return int(payload["sub"]), provider

@app.get("/api/integrations/google/connect")
def google_connect(user=Depends(current_user)):
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(503,"Google OAuth is not configured. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env")
    params={"client_id":settings.google_client_id,"redirect_uri":settings.google_redirect_uri,"response_type":"code","access_type":"offline","prompt":"consent","scope":" ".join(GOOGLE_SCOPES),"state":_oauth_state(user.id,"google")}
    return {"authorization_url":"https://accounts.google.com/o/oauth2/v2/auth?"+urllib.parse.urlencode(params)}

@app.get("/api/integrations/google/callback")
async def google_callback(code:str|None=None,state:str|None=None,error:str|None=None,db:Session=Depends(get_db)):
    if error: return RedirectResponse("/?integration_error="+urllib.parse.quote(error))
    if not code or not state: raise HTTPException(400,"Missing OAuth callback parameters")
    try: uid, provider=_parse_state(state)
    except Exception: raise HTTPException(400,"Invalid or expired OAuth state")
    if provider!="google": raise HTTPException(400,"Invalid provider")
    async with httpx.AsyncClient(timeout=30) as client:
        r=await client.post("https://oauth2.googleapis.com/token",data={"code":code,"client_id":settings.google_client_id,"client_secret":settings.google_client_secret,"redirect_uri":settings.google_redirect_uri,"grant_type":"authorization_code"})
        r.raise_for_status(); tok=r.json()
    x=db.scalar(select(Integration).where(Integration.user_id==uid,Integration.provider=="Google"))
    if not x: x=Integration(user_id=uid,provider="Google"); db.add(x)
    x.config_encrypted=encrypt_config(tok); x.connected=True; db.commit()
    return RedirectResponse("/#integrations&connected=Google")

@app.get("/api/integrations/shopify/connect")
def shopify_connect(shop:str,user=Depends(current_user)):
    if not settings.shopify_client_id or not settings.shopify_client_secret:
        raise HTTPException(503,"Shopify OAuth is not configured. Add SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET to .env")
    shop=shop.strip().lower().replace("https://","").replace("http://","").rstrip("/")
    if not shop.endswith(".myshopify.com"): shop += ".myshopify.com"
    state=_oauth_state(user.id,"shopify")
    params={"client_id":settings.shopify_client_id,"scope":"read_products,read_orders,read_customers","redirect_uri":settings.shopify_redirect_uri,"state":state}
    return {"authorization_url":f"https://{shop}/admin/oauth/authorize?"+urllib.parse.urlencode(params),"shop":shop}

@app.get("/api/integrations/shopify/callback")
async def shopify_callback(code:str|None=None,shop:str|None=None,state:str|None=None,db:Session=Depends(get_db)):
    if not code or not shop or not state: raise HTTPException(400,"Missing Shopify OAuth callback parameters")
    try: uid, provider=_parse_state(state)
    except Exception: raise HTTPException(400,"Invalid or expired OAuth state")
    if provider!="shopify": raise HTTPException(400,"Invalid provider")
    async with httpx.AsyncClient(timeout=30) as client:
        r=await client.post(f"https://{shop}/admin/oauth/access_token",json={"client_id":settings.shopify_client_id,"client_secret":settings.shopify_client_secret,"code":code})
        r.raise_for_status(); tok=r.json()
    tok["shop"]=shop
    x=db.scalar(select(Integration).where(Integration.user_id==uid,Integration.provider=="Shopify"))
    if not x: x=Integration(user_id=uid,provider="Shopify"); db.add(x)
    x.config_encrypted=encrypt_config(tok); x.connected=True; db.commit()
    return RedirectResponse("/#integrations&connected=Shopify")

async def _google_token(integration:Integration,db:Session):
    tok=decrypt_config(integration.config_encrypted or "")
    if not tok.get("refresh_token") and not tok.get("access_token"): raise HTTPException(401,"Google authorization is incomplete")
    if tok.get("refresh_token"):
        async with httpx.AsyncClient(timeout=30) as client:
            r=await client.post("https://oauth2.googleapis.com/token",data={"client_id":settings.google_client_id,"client_secret":settings.google_client_secret,"refresh_token":tok["refresh_token"],"grant_type":"refresh_token"})
            if r.is_success:
                fresh=r.json(); tok["access_token"]=fresh["access_token"]; tok.update({k:v for k,v in fresh.items() if k!="access_token"}); integration.config_encrypted=encrypt_config(tok); db.commit()
    return tok["access_token"]

@app.post("/api/integrations/google/sync")
async def google_sync(db:Session=Depends(get_db),user=Depends(current_user)):
    x=db.scalar(select(Integration).where(Integration.user_id==user.id,Integration.provider=="Google",Integration.connected==True))
    if not x: raise HTTPException(400,"Connect Google first")
    token=await _google_token(x,db)
    headers={"Authorization":f"Bearer {token}"}
    imported=0
    async with httpx.AsyncClient(timeout=30) as client:
        # Gmail: count sent messages as real email_sent events.
        r=await client.get("https://gmail.googleapis.com/gmail/v1/users/me/messages",headers=headers,params={"q":"in:sent","maxResults":100})
        if r.is_success:
            msgs=r.json().get("messages",[])
            for m in msgs:
                exists=db.scalar(select(Event).where(Event.user_id==user.id,Event.external_id==m.get("id")))
                if exists is None:
                    db.add(Event(user_id=user.id,event_type="email_sent",channel="Gmail",value=0,external_id=m.get("id"))); imported+=1
    db.commit()
    return {"ok":True,"provider":"Google","imported_events":imported,"note":"Gmail sent-message count is imported. Open-rate tracking requires an email delivery/tracking provider; Gmail mailbox access alone does not expose campaign opens."}

@app.post("/api/integrations/shopify/sync")
async def shopify_sync(db:Session=Depends(get_db),user=Depends(current_user)):
    x=db.scalar(select(Integration).where(Integration.user_id==user.id,Integration.provider=="Shopify",Integration.connected==True))
    if not x: raise HTTPException(400,"Connect Shopify first")
    tok=decrypt_config(x.config_encrypted or ""); shop=tok.get("shop"); access=tok.get("access_token")
    if not shop or not access: raise HTTPException(401,"Shopify authorization is incomplete")
    query="""query { orders(first:100, sortKey:CREATED_AT, reverse:true) { edges { node { id createdAt totalPriceSet { shopMoney { amount currencyCode } } customer { firstName lastName email } } } } }"""
    async with httpx.AsyncClient(timeout=30) as client:
        r=await client.post(f"https://{shop}/admin/api/2026-07/graphql.json",headers={"X-Shopify-Access-Token":access,"Content-Type":"application/json"},json={"query":query})
        r.raise_for_status(); data=r.json()
    orders=data.get("data",{}).get("orders",{}).get("edges",[])
    imported=0
    for edge in orders:
        o=edge["node"]; total=float(o["totalPriceSet"]["shopMoney"]["amount"] or 0)
        db.add(Event(user_id=user.id,event_type="revenue",channel="Shopify",value=total)); imported+=1
        cust=o.get("customer") or {}; email=cust.get("email")
        if email and not db.scalar(select(Contact).where(Contact.user_id==user.id,Contact.email==email)):
            name=((cust.get("firstName") or "")+" "+(cust.get("lastName") or "")).strip() or email
            db.add(Contact(user_id=user.id,name=name,email=email,source="Shopify"))
    db.commit()
    return {"ok":True,"provider":"Shopify","orders_imported":imported}



# ---------- Google Analytics 4 + Google Ads live reporting ----------
def _google_integration(db: Session, user_id: int) -> Integration:
    x = db.scalar(select(Integration).where(Integration.user_id == user_id, Integration.provider == "Google", Integration.connected == True))
    if not x:
        raise HTTPException(400, "Connect Google first. Reconnect after enabling the Google Ads scope if needed.")
    return x

@app.post("/api/integrations/google/analytics/config")
def google_analytics_config(property_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    property_id = property_id.strip().replace("properties/", "")
    if not property_id.isdigit():
        raise HTTPException(400, "GA4 Property ID must be numeric, for example 123456789")
    x = _google_integration(db, user.id)
    tok = decrypt_config(x.config_encrypted or "")
    tok["ga4_property_id"] = property_id
    x.config_encrypted = encrypt_config(tok)
    db.commit()
    return {"ok": True, "property_id": property_id}

@app.post("/api/integrations/google/analytics/sync")
async def google_analytics_sync(db: Session = Depends(get_db), user=Depends(current_user)):
    x = _google_integration(db, user.id)
    tok = decrypt_config(x.config_encrypted or "")
    property_id = tok.get("ga4_property_id") or settings.ga4_property_id
    if not property_id:
        raise HTTPException(400, "Set your GA4 Property ID first")
    access = await _google_token(x, db)
    body = {
        "dateRanges": [{"startDate": "30daysAgo", "endDate": "today"}],
        "dimensions": [{"name": "date"}],
        "metrics": [
            {"name": "activeUsers"},
            {"name": "newUsers"},
            {"name": "eventCount"},
            {"name": "totalRevenue"}
        ]
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport",
            headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
            json=body,
        )
        if not r.is_success:
            raise HTTPException(r.status_code, f"GA4 API error: {r.text[:800]}")
        data = r.json()
    imported = 0
    for row in data.get("rows", []):
        date = row.get("dimensionValues", [{}])[0].get("value", "")
        vals = [int(float(v.get("value", 0) or 0)) for v in row.get("metricValues", [])]
        active, new_users, event_count, revenue = (vals + [0,0,0,0])[:4]
        ext = f"ga4:{property_id}:{date}"
        if not db.scalar(select(Event).where(Event.user_id == user.id, Event.external_id == ext)):
            if active:
                db.add(Event(user_id=user.id, event_type="analytics_active_users", channel="Google Analytics", value=active, external_id=ext+":active"))
            if new_users:
                db.add(Event(user_id=user.id, event_type="analytics_new_users", channel="Google Analytics", value=new_users, external_id=ext+":new"))
            if event_count:
                db.add(Event(user_id=user.id, event_type="analytics_events", channel="Google Analytics", value=event_count, external_id=ext+":events"))
            if revenue:
                db.add(Event(user_id=user.id, event_type="revenue", channel="Google Analytics", value=float(revenue), external_id=ext+":revenue"))
            imported += 1
    db.commit()
    return {"ok": True, "provider": "Google Analytics", "property_id": property_id, "days_imported": imported}

@app.get("/api/integrations/google/ads/accounts")
async def google_ads_accounts(db: Session = Depends(get_db), user=Depends(current_user)):
    x = _google_integration(db, user.id)
    access = await _google_token(x, db)
    headers = {"Authorization": f"Bearer {access}"}
    if settings.google_ads_developer_token:
        headers["developer-token"] = settings.google_ads_developer_token
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get("https://googleads.googleapis.com/v25/customers:listAccessibleCustomers", headers=headers)
        if not r.is_success:
            raise HTTPException(r.status_code, f"Google Ads API error: {r.text[:800]}")
        data = r.json()
    ids = [x.rsplit("/", 1)[-1] for x in data.get("resourceNames", [])]
    return {"accounts": ids}

@app.post("/api/integrations/google/ads/config")
def google_ads_config(customer_id: str, login_customer_id: str | None = None, db: Session = Depends(get_db), user=Depends(current_user)):
    customer_id = customer_id.strip().replace("-", "")
    if not customer_id.isdigit() or len(customer_id) != 10:
        raise HTTPException(400, "Google Ads customer ID must be 10 digits")
    x = _google_integration(db, user.id)
    tok = decrypt_config(x.config_encrypted or "")
    tok["google_ads_customer_id"] = customer_id
    if login_customer_id:
        tok["google_ads_login_customer_id"] = login_customer_id.strip().replace("-", "")
    x.config_encrypted = encrypt_config(tok)
    db.commit()
    return {"ok": True, "customer_id": customer_id}

@app.post("/api/integrations/google/ads/sync")
async def google_ads_sync(db: Session = Depends(get_db), user=Depends(current_user)):
    x = _google_integration(db, user.id)
    tok = decrypt_config(x.config_encrypted or "")
    customer_id = tok.get("google_ads_customer_id") or settings.google_ads_customer_id
    if not customer_id:
        raise HTTPException(400, "Set your Google Ads customer ID first")
    customer_id = str(customer_id).replace("-", "")
    access = await _google_token(x, db)
    headers = {"Authorization": f"Bearer {access}", "Content-Type": "application/json"}
    if settings.google_ads_developer_token:
        headers["developer-token"] = settings.google_ads_developer_token
    login_id = tok.get("google_ads_login_customer_id") or settings.google_ads_login_customer_id
    if login_id:
        headers["login-customer-id"] = str(login_id).replace("-", "")
    query = """SELECT campaign.id, campaign.name, campaign.status, metrics.impressions, metrics.clicks, metrics.ctr, metrics.conversions, metrics.conversions_value, metrics.cost_micros FROM campaign WHERE segments.date DURING LAST_30_DAYS AND campaign.status != 'REMOVED'"""
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"https://googleads.googleapis.com/{settings.google_ads_api_version}/customers/{customer_id}/googleAds:searchStream",
            headers=headers,
            json={"query": query},
        )
        if not r.is_success:
            raise HTTPException(r.status_code, f"Google Ads API error: {r.text[:1000]}")
        payload = r.json()
    results = []
    for chunk in payload if isinstance(payload, list) else [payload]:
        results.extend(chunk.get("results", []))
    updated = 0
    for row in results:
        camp = row.get("campaign", {})
        metrics = row.get("metrics", {})
        name = camp.get("name") or f"Google Ads {camp.get('id')}"
        impressions = int(metrics.get("impressions", 0) or 0)
        clicks = int(metrics.get("clicks", 0) or 0)
        conversions = int(float(metrics.get("conversions", 0) or 0))
        spend = float(metrics.get("costMicros", 0) or 0) / 1_000_000
        revenue = float(metrics.get("conversionsValue", 0) or 0)
        c = db.scalar(select(Campaign).where(Campaign.user_id == user.id, Campaign.channel == "Google Ads", Campaign.name == name))
        if not c:
            c = Campaign(user_id=user.id, name=name, channel="Google Ads", audience="Google Ads", status=str(camp.get("status", "UNKNOWN")), budget=0)
            db.add(c)
        c.status = str(camp.get("status", c.status))
        c.impressions = impressions
        c.clicks = clicks
        c.conversions = conversions
        c.spend = spend
        c.revenue = revenue
        c.updated_at = datetime.now(timezone.utc)
        updated += 1
    db.commit()
    return {"ok": True, "provider": "Google Ads", "campaigns_updated": updated, "customer_id": customer_id}

PROVIDERS=["Gmail","Shopify","Slack","Meta Ads","Google Ads","Google Analytics","Mailchimp"]
@app.get("/api/integrations",response_model=list[IntegrationOut])
def integrations(db:Session=Depends(get_db),user=Depends(current_user)):
    existing={x.provider:x for x in db.scalars(select(Integration).where(Integration.user_id==user.id)).all()}
    return [{"provider":p,"connected":existing[p].connected if p in existing else False,"updated_at":existing[p].updated_at if p in existing else None} for p in PROVIDERS]

@app.post("/api/integrations")
def save_integration(data:IntegrationIn,db:Session=Depends(get_db),user=Depends(current_user)):
    if data.provider not in PROVIDERS: raise HTTPException(400,"Unsupported provider")
    x=db.scalar(select(Integration).where(Integration.user_id==user.id,Integration.provider==data.provider))
    if not x: x=Integration(user_id=user.id,provider=data.provider); db.add(x)
    x.config_encrypted=encrypt_config(data.config); x.connected=True; db.commit(); return {"provider":x.provider,"connected":True}

@app.delete("/api/integrations/{provider}")
def disconnect(provider:str,db:Session=Depends(get_db),user=Depends(current_user)):
    x=db.scalar(select(Integration).where(Integration.user_id==user.id,Integration.provider==provider))
    if x: x.connected=False; x.config_encrypted=None; db.commit()
    return {"ok":True}

@app.get("/api/drafts",response_model=list[DraftOut])
def drafts(db:Session=Depends(get_db),user=Depends(current_user)):
    return db.scalars(select(ContentDraft).where(ContentDraft.user_id==user.id).order_by(ContentDraft.created_at.desc())).all()

@app.post("/api/drafts",response_model=DraftOut)
def create_draft(data:DraftIn,db:Session=Depends(get_db),user=Depends(current_user)):
    d=ContentDraft(user_id=user.id,**data.model_dump()); db.add(d); db.commit(); db.refresh(d); return d

@app.delete("/api/drafts/{did}")
def delete_draft(did:int,db:Session=Depends(get_db),user=Depends(current_user)):
    d=db.scalar(select(ContentDraft).where(ContentDraft.id==did,ContentDraft.user_id==user.id))
    if not d: raise HTTPException(404,"Draft not found")
    db.delete(d); db.commit(); return {"ok":True}

@app.post("/api/ai/generate")
async def ai_generate(data:AIIn,user=Depends(current_user)):
    try: text=await generate_ai(data.prompt,data.channel)
    except Exception as e: raise HTTPException(400,str(e))
    return {"text":text,"model":settings.openai_model}

@app.put("/api/settings")
def settings_update(data:SettingsIn,db:Session=Depends(get_db),user=Depends(current_user)):
    name, email, notifications = data.name, data.email, data.notifications
    if email and email.lower()!=user.email:
        if db.scalar(select(User).where(User.email==email.lower())): raise HTTPException(409,"Email already in use")
        user.email=email.lower()
    if name is not None: user.name=name.strip()
    if notifications is not None: user.notifications=notifications
    db.commit(); return UserOut.model_validate(user)

@app.get("/",include_in_schema=False)
def index(): return FileResponse(FRONT/"index.html")
@app.get("/{path:path}",include_in_schema=False)
def static(path:str):
    p=FRONT/path
    if p.is_file(): return FileResponse(p)
    return FileResponse(FRONT/"index.html")
