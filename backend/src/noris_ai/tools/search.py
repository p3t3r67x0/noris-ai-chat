"""Typed search handler binding; admission, persistence and events stay in P1b/P2."""

import asyncio
from collections.abc import Awaitable, Callable

from noris_ai.chat.repository import utc_now
from noris_ai.tools.cancellation import GenerationToolContext
from noris_ai.tools.errors import ToolError
from noris_ai.tools.providers.searxng import SearXNGProvider
from noris_ai.tools.registry import canonical_payload, validate_payload
from noris_ai.tools.schemas import SearchInput, SearchResult


def search_handler(
    provider: SearXNGProvider, *, max_output_bytes: int
) -> Callable[[GenerationToolContext, SearchInput], Awaitable[SearchResult]]:
    async def handler(context: GenerationToolContext, value: SearchInput) -> SearchResult:
        context.check()
        if context.provider_key != "searxng" or context.config_version != provider.config_version:
            raise ToolError("TOOL_FORBIDDEN")
        if context.permission_scope != "web_search":
            raise ToolError("TOOL_FORBIDDEN")
        if context.budget.calls != 1 or context.budget.bytes < max_output_bytes:
            raise ToolError("BUDGET_LIMIT")
        async with asyncio.timeout(max(0, (context.deadline_at - utc_now()).total_seconds())):
            result = await provider.search(value)
        context.check()
        validated = validate_payload(
            SearchResult, canonical_payload(result), max_output_bytes, output=True
        )
        if (
            validated.provider != context.provider_key
            or validated.config_version != context.config_version
        ):
            raise ToolError("TOOL_OUTPUT_INVALID")
        return validated

    return handler
