#!/usr/bin/env python3
"""
YouTube 8K Agent - AI Agent that checks YouTube video quality using LangChain

This agent:
1. Runs daily at 6:30 AM (configurable)
2. Opens YouTube Studio and finds all private videos from the last 2 months
3. Opens each on YouTube and checks for 8K resolution availability
4. Sends a list of URLs with 8K support status to Telegram

Usage:
  python run.py
  curl -X POST http://localhost:8111/run
"""
import logging
import uvicorn
logging.basicConfig(level=logging.INFO)
if __name__ == "__main__":
    uvicorn.run("app.service:app", host="0.0.0.0", port=8111, reload=False)