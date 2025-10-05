from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os

from .llm_client import chat as llm_chat
from .scheduler import scheduler, add_oneoff_job, list_jobs, get_job

app = FastAPI(title="LLM Cloud Starter", version="0.1.0")

# Serve a simple control panel at /ui/control.html
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")

@app.get("/", response_class=HTMLResponse)
def root():
    return '<meta charset="utf-8"><a href="/ui/control.html">Open LLM Control Panel</a>'


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔐 beveiliging
def verify_key(x_api_key: str | None = Header(default=None)):
    expected = os.getenv("API_ACCESS_KEY")
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

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

@app.on_event("startup")
async def on_startup():
    scheduler.start()

@app.get("/health")
def health():
    return {"status": "ok"}

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
        job_id = await add_oneoff_job(req.task, req.payload)
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
