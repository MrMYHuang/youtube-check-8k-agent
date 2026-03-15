from typing import Any, Dict

from .browser_task import run_check_8k


async def run_agent() -> Dict[str, Any]:
    return await run_check_8k()
