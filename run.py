#!/usr/bin/env python3
"""
YouTube 8K Agent - AI Agent that checks YouTube video quality using LangChain

This agent:
1. Runs daily at 6:30 AM (configurable)
2. Opens YouTube Studio and finds the first private video
3. Opens it on YouTube and checks for 8K resolution availability
4. Sends results to Telegram

Usage:
  python run.py
  curl -X POST http://localhost:8000/run
"""
#!/usr/bin/env python3
import logging
import uvicorn
logging.basicConfig(level=logging.INFO)
if __name__ == "__main__":
    uvicorn.run("app.service:app", host="0.0.0.0", port=8111, reload=False)