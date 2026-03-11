import json
import logging
from typing import Any, Dict

from langchain_community.tools import StructuredTool
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from .browser_task import run_check_8k
from .config import settings

logger = logging.getLogger(__name__)


async def _run_check_tool() -> str:
    result = await run_check_8k()
    return json.dumps(result)


def _build_agent():
    llm = ChatOllama(base_url=settings.ollama_base_url, model=settings.ollama_model)
    tool = StructuredTool.from_function(
        coroutine=_run_check_tool,
        name="check_youtube_8k",
        description=(
            "Runs the YouTube Studio workflow to find all private videos from "
            "the last 2 months, open each on YouTube, and detect whether 8K "
            "(4320p) is available. Returns JSON with a videos list and status."
        ),
    )

    return create_react_agent(
        llm,
        [tool],
        prompt="You are a helpful assistant that checks YouTube videos for 8K availability.",
    )


async def run_agent() -> Dict[str, Any]:
    agent = _build_agent()
    try:
        result = await agent.ainvoke(
            {"messages": [("human", "Check all private videos from the last 2 months for 8K availability.")]}
        )

        # Extract the last AI message content
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, "content") and isinstance(msg.content, str):
                try:
                    return json.loads(msg.content)
                except json.JSONDecodeError:
                    continue

        logger.warning("Agent returned non-JSON output, running tool directly")
        return await run_check_8k()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Agent failed, running tool directly: %s", exc)
        return await run_check_8k()
