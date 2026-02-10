import json
import logging
from typing import Any, Dict

from langchain_community.tools import StructuredTool
from langchain_ollama import ChatOllama
from langchain.agents import create_agent

from .browser_task import run_check_8k
from .config import settings

logger = logging.getLogger(__name__)


async def _run_check_tool() -> str:
    result = await run_check_8k()
    return json.dumps(result)


def _build_agent() -> Any:
    llm = ChatOllama(base_url=settings.ollama_base_url, model=settings.ollama_model)
    tool = StructuredTool.from_function(
        coroutine=_run_check_tool,
        name="check_youtube_8k",
        description=(
            "Runs the YouTube Studio workflow to find the first private video, "
            "open it on YouTube, and detect whether 8K (4320p) is available. "
            "Returns JSON with video_title, video_url, has_8k, status, error."
        ),
    )

    agent = create_agent(llm, tools=[tool])
    return agent


async def run_agent() -> Dict[str, Any]:
    agent = _build_agent()
    try:
        output = await agent.ainvoke(
            {"input": "Check the first private video for 8K availability."}
        )

        if "messages" not in output:
            raise RuntimeError("Agent did not return messages")

        last_msg = output["messages"][-1]
        try:
            if hasattr(last_msg, "content"):
                content = last_msg.content
                if isinstance(content, str):
                    return json.loads(content)
            raise RuntimeError("Invalid response format")
        except json.JSONDecodeError as exc:
            logger.exception("Failed to parse agent output: %s", last_msg)
            raise RuntimeError("Invalid agent output") from exc
    except Exception as exc:  # noqa: BLE001
        # Ollama sometimes returns an empty stream while loading a model.
        # Fallback to direct task execution to keep the service reliable.
        logger.warning("Agent failed, running tool directly: %s", exc)
        return await run_check_8k()
