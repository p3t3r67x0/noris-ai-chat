"""Typed web.fetch.v1 binding; the existing runtime owns admission and commits."""

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

from noris_ai.chat.repository import utc_now
from noris_ai.tools.cancellation import GenerationToolContext
from noris_ai.tools.errors import ToolError
from noris_ai.tools.providers.source_fetch import SourceFetchProvider
from noris_ai.tools.registry import canonical_payload, validate_payload
from noris_ai.tools.schemas import FetchInput, SearchSource, SourceDocument

SourceResolver = Callable[[GenerationToolContext, UUID], Awaitable[SearchSource]]


def fetch_handler(
    provider: SourceFetchProvider, resolver: SourceResolver, *, max_output_bytes: int
) -> Callable[[GenerationToolContext, FetchInput], Awaitable[SourceDocument]]:
    async def handler(context: GenerationToolContext, value: FetchInput) -> SourceDocument:
        context.check()
        if (
            context.provider_key != "public_source"
            or context.config_version != provider.config_version
            or context.permission_scope != "web_fetch"
        ):
            raise ToolError("TOOL_FORBIDDEN")
        if context.budget.calls != 1 or context.budget.bytes < max_output_bytes:
            raise ToolError("BUDGET_LIMIT")
        async with asyncio.timeout(max(0, (context.deadline_at - utc_now()).total_seconds())):
            source = await resolver(context, value.source_id)
            context.check()
            if source.source_id != value.source_id:
                raise ToolError("TOOL_FORBIDDEN")
            result = await provider.fetch(
                context, source.source_id, str(source.url), max_output_bytes=max_output_bytes
            )
        validated = validate_payload(
            SourceDocument, canonical_payload(result), max_output_bytes, output=True
        )
        if validated.source_id != value.source_id:
            raise ToolError("TOOL_OUTPUT_INVALID")
        context.check()
        return validated

    return handler
