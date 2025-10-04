# LLM Cloud Starter (FastAPI + APScheduler + LiteLLM)
A minimal, provider-agnostic LLM microservice you can deploy in minutes.

## What you get
- **FastAPI** REST API (`/health`, `/chat`, `/jobs/*`)
- **LiteLLM** to talk to OpenAI/Anthropic/Groq/etc. by changing env vars only
- **APScheduler** for lightweight job scheduling (one-off + recurring)
- **Dockerfile** for any platform; **Render** one-click style `render.yaml`
- **.github/workflows/schedule.yml** example hourly trigger hitting your API

## Quick start (local)
1. Create a virtualenv and install:
   ```bash
   python -m venv .venv && . .venv/bin/activate  # Windows: .\.venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env
   # Edit .env with your keys and model (see below)
   uvicorn app.main:app --reload
   ```
2. Try the endpoints:
   ```bash
   curl http://localhost:8000/health
   curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"Schrijf een haiku over Rotterdam."}]}' 
   ```

## Configure your model/provider
This starter uses **LiteLLM** so you can switch models without code changes.

Environment variables (see `.env.example`):
- `LLM_MODEL` — e.g. `openai/gpt-4o-mini`, `anthropic/claude-3.5-sonnet`, `groq/llama-3.1-70b-versatile`
- API keys:
  - OpenAI: `OPENAI_API_KEY`
  - Anthropic: `ANTHROPIC_API_KEY`
  - Groq: `GROQ_API_KEY`
- (Optional) `LLM_TEMPERATURE` (default 0.3)

> Tip: Only set the key(s) for the provider you use.

## Deploy to Render (simple & free tier available)
1. Push this folder to a new GitHub repo.
2. In [Render](https://render.com) create a **Web Service** from that repo.
3. **Environment**: `Python 3.11` (or higher)
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Add environment variables from your `.env` (Render → Settings → Environment).  
7. Deploy. Your API will be live at `https://<your-service>.onrender.com`.

## Scheduling options
- **APScheduler in-app** for cron/interval jobs (see `app/scheduler.py`).
- **GitHub Actions** (see `.github/workflows/schedule.yml`) to call a task endpoint on a schedule.
- Render's **Cron Jobs** (optional) to hit any endpoint regularly.

## Endpoints
- `GET /health` → {"status":"ok"}
- `POST /chat` → simple chat; body: `{"messages":[{role,content},...]}`
- `POST /jobs/create` → schedule a one-off job; body: `{"task":"summarize","payload":{...}}`
- `GET /jobs` → list scheduled jobs
- `GET /jobs/{job_id}` → job details

## Extend with your own tasks
Add functions in `app/tasks.py` and register them in `TASK_REGISTRY`. Examples included:
- `summarize`: summarize text with your model
- `rewrite`: rewrite text with simple rule tuning

## Security
- Keep your API private if needed (Render Access Control / auth middleware).
- Never commit real API keys. Use environment variables or Render Secrets.

## License
MIT — do anything, no warranty.
