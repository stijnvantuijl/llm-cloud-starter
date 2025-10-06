from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import os, time, base64, logging
from collections import defaultdict, deque

from .llm_client import chat as llm_chat
from .scheduler import scheduler, add_oneoff_job, list_jobs, get_job

# ---------- App ----------
app = FastAPI(title="LLM Cloud Starter", version="0.2.0")

# CORS (strakker maken als je klaar bent)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # bv. ["https://<jouw-service>.onrender.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Static UI ----------
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")

# ---------- Security ----------
def verify_key(x_api_key: str | None = Header(default=None)):
    expected = os.getenv("API_ACCESS_KEY")
    old = os.getenv("API_ACCESS_KEY_OLD")  # optioneel voor key-rotatie
    if not expected or (x_api_key != expected and (not old or x_api_key != old)):
        raise HTTPException(status_code=401, detail="Unauthorized")

def basic_auth(request: Request):
    """Optional Basic Auth for UI. Set UI_BASIC_USER / UI_BASIC_PASS to enable."""
    user = os.getenv("UI_BASIC_USER")
    pwd  = os.getenv("UI_BASIC_PASS")
    if not user or not pwd:
        return
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("basic "):
        raise HTTPException(status_code=401, detail="Auth required", headers={"WWW-Authenticate":"Basic"})
    raw = base64.b64decode(auth.split(" ",1)[1]).decode("utf-8", "ignore")
    u, _, p = raw.partition(":")
    if u != user or p != pwd:
        raise HTTPException(status_code=401, detail="Invalid credentials", headers={"WWW-Authenticate":"Basic"})

# ---------- Rate limits & caps ----------
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "120"))
_window = 60
_buckets = defaultdict(deque)
_req_log = deque()
log = logging.getLogger("uvicorn.error")

@app.middleware("http")
async def ratelimit_mw(request: Request, call_next):
    try:
        api_k = request.headers.get("X-API-Key") or request.client.host
        now = time.time()
        q = _buckets[api_k]
        while q and now - q[0] > _window:
            q.popleft()
        if RATE_LIMIT_PER_MIN and len(q) >= RATE_LIMIT_PER_MIN:
            return JSONResponse({"detail":"rate limit"}, status_code=429)
        q.append(now)
    except Exception:
        pass
    return await call_next(request)

@app.middleware("http")
async def hourly_cap_mw(request: Request, call_next):
    MAX_REQ_PER_HOUR = int(os.getenv("MAX_REQ_PER_HOUR", "0"))  # 0=uit
    if MAX_REQ_PER_HOUR:
        now = time.time()
        while _req_log and now - _req_log[0] > 3600:
            _req_log.popleft()
        if len(_req_log) >= MAX_REQ_PER_HOUR:
            return JSONResponse({"detail":"hourly cap reached"}, status_code=429)
        _req_log.append(now)
    return await call_next(request)

@app.middleware("http")
async def access_log_mw(request: Request, call_next):
    start = time.time()
    resp = await call_next(request)
    dur = int((time.time()-start)*1000)
    log.info("%s %s %s -> %s %dms", request.client.host, request.method, request.url.path, resp.status_code, dur)
    return resp

# ---------- Models ----------
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    system: Optional[str] = None
    temperature: Optional[float] = None

class JobCreateRequest(BaseModel):
    task: str = Field(..., description="task name, e.g. 'summarize'")
    payload: Dict[str, Any] = Field(default_factory=dict)

# ---------- Lifecycle ----------
@app.on_event("startup")
async def on_startup():
    scheduler.start()

# ---------- Routes ----------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/self-test")
async def self_test(_=Depends(verify_key)):
    try:
        txt = await llm_chat([{"role": "user", "content": "Antwoord met slechts: OK"}], temperature=0)
        ok = isinstance(txt, str) and "OK" in txt
        return {"ok": ok, "output": txt}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/")
def root(_=Depends(basic_auth)):
    return RedirectResponse(url="/ui/control.html")

@app.get("/ui/control.html", response_class=HTMLResponse)
def guard_ui(_=Depends(basic_auth)):
    with open(os.path.join(STATIC_DIR, "control.html"), "r", encoding="utf-8") as f:
        return f.read()

@app.post("/chat")
async def chat(req: ChatRequest, _=Depends(verify_key)):
    messages = [m.model_dump() for m in req.messages]
    try:
        text = await llm_chat(messages, system=req.system, temperature=req.temperature)
        return {"output": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/jobs/create")
async def create_job(req: JobCreateRequest, _=Depends(verify_key)):
    try:
from anyio import to_thread
job_id = await to_thread.run_sync(add_oneoff_job, req.task, req.payload)
        return {"job_id": job_id}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@app.get("/jobs")
async def jobs(_=Depends(verify_key)):
    return list_jobs()

@app.get("/jobs/{job_id}")
async def job(job_id: str, _=Depends(verify_key)):
    j = get_job(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="job not found")
    return j

