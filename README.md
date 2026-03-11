# YouTube 8K Agent

Runs a daily (6:30 AM) check on all private videos of recent 2 months in YouTube Studio, opens each on YouTube, checks for 8K (4320p) in the quality menu, and sends a list of URLs with 8K support status to Telegram. It also exposes a REST API to trigger manually.

## Setup

1. Install dependencies

```bash
uv venv .venv
source .venv/bin/activate
uv sync
python -m playwright install chromium
```

2. Configure environment

```bash
cp .env.example .env
```

Update values in `.env`.

3. First-time login

Run the service once with `HEADLESS=false`, then complete YouTube login in the opened Chromium window. The session is stored under `YOUTUBE_USER_DATA_DIR` so future runs can be headless.

## Run

```bash
python run.py
```

## Manual trigger

```bash
curl -X POST http://localhost:8111/run
```

## Health

```bash
curl http://localhost:8111/health
```

## Notes

- The selector logic is tuned for YouTube Studio’s current UI. If the page layout changes, update selectors in `app/browser_task.py`.- Videos older than 2 months are skipped; the agent scrolls through YouTube Studio's video list until it passes the cutoff date.- The task uses a LangChain agent with an Ollama-backed local LLM to orchestrate tool execution.
