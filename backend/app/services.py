import json, base64, hashlib
from cryptography.fernet import Fernet
from .config import settings

def _fernet():
    key = settings.encryption_key or base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest()).decode()
    return Fernet(key.encode())

def encrypt_config(data: dict) -> str:
    f = _fernet()
    raw = json.dumps(data).encode()
    return f.encrypt(raw).decode()

def decrypt_config(value: str) -> dict:
    f = _fernet()
    try:
        raw = f.decrypt(value.encode())
        return json.loads(raw)
    except Exception: return {}

async def generate_ai(prompt: str, channel: str):
    if not settings.openai_api_key:
        # Fully local fallback so Content Studio remains usable without paid API credentials.
        topic = prompt.strip().rstrip(".")
        templates = {
            "Email": f"Subject: {topic[:70]}\n\nHi there,\n\nWe are excited to share {topic}.\n\nDiscover the key benefits, see what makes it useful, and take the next step when you are ready.\n\nBest regards,\nFlowPilot AI",
            "LinkedIn": f"We are sharing an update about {topic}.\n\nHere are the key points: clear value, practical benefits, and a simple next step.\n\nWhat would you add to the conversation?",
            "Instagram": f"✨ {topic}\n\nMake the value clear. Keep the message simple. Give your audience one useful reason to act today.\n\n#Marketing #Growth #FlowPilotAI",
            "Blog": f"# {topic}\n\n## Why it matters\nExplain the customer problem, the value of the solution, and the practical outcome.\n\n## Key benefits\n- Clear customer value\n- Simple next steps\n- Measurable outcomes",
            "Ad": f"{topic}\n\nClear value. Simple next step.\n\nLearn more today."
        }
        return templates.get(channel, templates["Email"])
    import httpx
    body = {
        "model": settings.openai_model,
        "input": f"Create a high-quality {channel} marketing asset. User request: {prompt}. Return only the finished copy with a short title first."
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post("https://api.openai.com/v1/responses", headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    text = data.get("output_text")
    if text: return text
    parts=[]
    for item in data.get("output", []):
        for c in item.get("content", []):
            if c.get("type") == "output_text": parts.append(c.get("text", ""))
    return "\n".join(parts).strip()
