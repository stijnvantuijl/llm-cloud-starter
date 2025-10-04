from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import os

from .llm_client import chat as llm_chat
from .scheduler import scheduler, add_oneoff_job, list_jobs, get_job

app = FastAPI(title="LLM Cloud Starter", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
async def chat(req: ChatRequest):
    messages = [m.model_dump() for m in req.messages]
    try:
        text = await llm_chat(messages, system=req.system, temperature=req.temperature)
        return {"output": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/jobs/create")
async def create_job(req: JobCreateRequest):
    try:
        job_id = await add_oneoff_job(req.task, req.payload)
        return {"job_id": job_id}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@app.get("/jobs")
async def jobs():
    return list_jobs()

@app.get("/jobs/{job_id}")
async def job(job_id: str):
    j = get_job(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="job not found")
    return j
