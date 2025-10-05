import os, httpx, datetime

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

def _today_utc_start_iso():
    return datetime.datetime.utcnow().date().isoformat() + "T00:00:00Z"

async def get_token():
    tenant = os.getenv("MS_TENANT_ID")
    client_id = os.getenv("MS_CLIENT_ID")
    client_secret = os.getenv("MS_CLIENT_SECRET")
    if not all([tenant, client_id, client_secret]):
        raise RuntimeError("Missing MS_TENANT_ID / MS_CLIENT_ID / MS_CLIENT_SECRET")
    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
        "scope": "https://graph.microsoft.com/.default",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(token_url, data=data)
        r.raise_for_status()
        return r.json()["access_token"]

async def list_today_messages(user_id: str, top: int = 50):
    access_token = await get_token()
    params = {
        "$top": str(top),
        "$orderby": "receivedDateTime desc",
        "$filter": f"receivedDateTime ge {_today_utc_start_iso()}",
        "$select": "subject,from,receivedDateTime,bodyPreview"
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{GRAPH_BASE}/users/{user_id}/messages"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
    items = []
    for m in data.get("value", []):
        frm = (m.get("from") or {}).get("emailAddress") or {}
        items.append({
            "subject": m.get("subject") or "",
            "from": frm.get("address") or "",
            "snippet": (m.get("bodyPreview") or "")[:1200],
            "date": m.get("receivedDateTime") or "",
        })
    return items

async def send_mail_plain(user_id: str, to: str, subject: str, body_text: str):
    access_token = await get_token()
    url = f"{GRAPH_BASE}/users/{user_id}/sendMail"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body_text},
            "toRecipients": [{"emailAddress": {"address": to}}],
        },
        "saveToSentItems": True
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return True
