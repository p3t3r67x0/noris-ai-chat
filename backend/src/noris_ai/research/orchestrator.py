"""Trusted server pipeline; runtime owns I/O, persistence, budgets and events."""

import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta
from time import monotonic
from uuid import UUID, uuid5

from pydantic import ValidationError

from noris_ai.chat.repository import ChatRepository, utc_now
from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.schemas import PersistedChatRequest
from noris_ai.research.grounding import FetchedSource, GroundingContextBuilder
from noris_ai.research.planner import plan_research
from noris_ai.research.schemas import (
    ResearchActivation,
    ResearchIntent,
    ResearchProjection,
    ResearchState,
    UnavailableSource,
)
from noris_ai.research.selection import SavedSearch, select_sources
from noris_ai.tools.budget import BudgetCoordinator
from noris_ai.tools.errors import ToolError
from noris_ai.tools.registry import canonical_payload
from noris_ai.tools.runtime import ToolRuntime
from noris_ai.tools.schemas import (
    FetchInput,
    SearchResult,
    SourceDocument,
    ToolRunCreate,
    ToolSchema,
)

logger = logging.getLogger(__name__)


class ResearchOrchestrator:
    def __init__(
        self,
        config: Settings,
        chat: ChatRepository,
        gateway: LLMGateway,
        tools: ToolRuntime,
    ) -> None:
        self.config, self.chat, self.gateway, self.tools = config, chat, gateway, tools

    async def prepare(
        self,
        request: PersistedChatRequest,
        activation: ResearchActivation | ResearchIntent,
        check_cancel: Callable[[], None],
    ) -> PersistedChatRequest:
        """Returns an already admitted request; caller uses the existing gateway stream.

        No output from the LLM is ever read as a plan or a subsequent action.
        Reentry is rejected by the existing generation scope and durable claim.
        """
        if not self.config.research_enabled:
            raise LLMError("RESEARCH_DISABLED", 403)
        owner = (
            activation.owner_id
            if isinstance(activation, ResearchActivation)
            else self.config.chat_owner_id
        )
        if owner != self.config.chat_owner_id:
            raise LLMError("RESEARCH_INVALID", 403)
        generation = UUID(request.generationId)
        conversation = UUID(request.conversationId)
        deadline = utc_now() + timedelta(seconds=self.config.research_timeout_seconds)
        projection: ResearchProjection | None = None
        admitted = False
        prepared = False
        phase_started = monotonic()

        async def fence() -> None:
            check_cancel()
            if utc_now() >= deadline:
                raise LLMError("TIMEOUT", 504)
            await self.chat.check_generation_live(owner, generation)
            check_cancel()

        async def stage(state: ResearchState, **updates: object) -> None:
            nonlocal projection, phase_started
            await fence()
            if projection is None:
                raise LLMError("RESEARCH_FAILED")
            previous = projection.state
            updated = ResearchProjection.model_validate_json(
                projection.model_copy(update={"state": state, **updates}).model_dump_json()
            )
            await self.chat.update_research(owner, updated, previous)
            projection = updated
            logger.info(
                "Research phase finished",
                extra={
                    "research_phase": previous,
                    "elapsed_ms": (monotonic() - phase_started) * 1000,
                },
            )
            phase_started = monotonic()
            check_cancel()

        try:
            async with asyncio.timeout(self.config.research_timeout_seconds):
                await fence()
                question = await self.chat.research_question(owner, request)
                plan = plan_research(
                    question,
                    activation.language,
                    deadline,
                    explicit=activation.explicit
                    if isinstance(activation, ResearchActivation)
                    else True,
                )
                model, capacity = await self.gateway.research_capacity(request)
                if plan.intent == "not_required":
                    projection = await self.chat.claim_research(owner, generation, plan)
                    await stage("skipped")
                    await self.gateway.reserve(request)
                    admitted = True
                    await fence()
                    prepared = True
                    return request
                if capacity < 1200:
                    raise LLMError("CONTEXT_LIMIT", 413)
                permissions = {
                    tool: self.tools.policy.require(self.tools.registry.get(tool))
                    for tool in ("web.search.v1", "web.fetch.v1")
                }
                if any(p.decision != "allow" for p in permissions.values()):
                    raise LLMError("RESEARCH_APPROVAL_REQUIRED", 403)
                requirements = [
                    (p.per_call, p.daily_limit, p.generation_limit, p.currency)
                    for tool, count in (
                        ("web.search.v1", len(plan.searches)),
                        ("web.fetch.v1", plan.max_fetches),
                    )
                    for p in [permissions[tool]]
                    for _ in range(count)
                ]
                await BudgetCoordinator(self.chat.database).check_tool_capacity(
                    owner,
                    generation,
                    requirements,
                )
                await fence()
                # Hold the regular gateway slot and durable text ceiling across
                # research. Final content is checked against this ceiling at dispatch.
                await self.gateway.reserve(request, input_token_reserve=capacity)
                admitted = True
                await fence()
                # Only now is public intent converted into trusted activation:
                # persisted scope, model, context, both permissions, budget and
                # cancel fences have passed the one existing admission path.
                trusted = (
                    activation
                    if isinstance(activation, ResearchActivation)
                    else ResearchActivation(owner, activation.language, explicit=True)
                )
                projection = await self.chat.claim_research(trusted.owner_id, generation, plan)
                calls = 0

                async def call(
                    tool: str,
                    step: str,
                    value: ToolSchema,
                    search_run: UUID | None = None,
                ) -> tuple[UUID, SearchResult | SourceDocument]:
                    nonlocal calls
                    await fence()
                    if calls >= plan.max_tool_calls:
                        raise LLMError("BUDGET_LIMIT", 429)
                    permission = self.tools.policy.require(self.tools.registry.get(tool))
                    if permission != permissions[tool]:
                        raise LLMError("RESEARCH_FAILED", 403)
                    run_id = uuid5(generation, step)
                    calls += 1
                    await self.tools.execute(
                        trusted.owner_id,
                        ToolRunCreate(
                            id=run_id,
                            conversation_id=conversation,
                            generation_id=generation,
                            tool_id=tool,
                            step_key=step,
                            invocation_kind="research_step",
                            source_search_run_id=search_run,
                            provider_key=permission.provider_key,
                            config_version=permission.config_version,
                            deadline_at=plan.deadline_at,
                        ),
                        canonical_payload(value),
                    )
                    await fence()
                    output = await self.tools.repository.research_result(
                        owner,
                        conversation,
                        generation,
                        run_id,
                        tool,
                        self.tools.policy,
                    )
                    return run_id, output

                await stage("searching")
                searches: list[SavedSearch] = []
                for index, search in enumerate(plan.searches):
                    run, result = await call("web.search.v1", f"research.v1.search.{index}", search)
                    if not isinstance(result, SearchResult) or len(result.sources) > search.limit:
                        raise LLMError("RESEARCH_FAILED")
                    searches.append(SavedSearch(run, result))
                await stage("selecting")
                selected = select_sources(
                    question, searches, min(plan.max_fetches, max(1, capacity // 4000))
                )
                await stage("fetching")
                documents: list[FetchedSource] = []
                unavailable: list[UnavailableSource] = []
                for index, source in enumerate(selected):
                    step = f"research.v1.fetch.{index}"
                    try:
                        run, result = await call(
                            "web.fetch.v1",
                            step,
                            FetchInput(source_id=source.source.source_id),
                            source.search_run_id,
                        )
                        if not isinstance(result, SourceDocument):
                            raise LLMError("RESEARCH_FAILED")
                        documents.append(FetchedSource(source, run, result))
                    except ToolError as error:
                        await fence()
                        if error.code not in ("PROVIDER_ERROR", "TOOL_OUTPUT_INVALID"):
                            raise
                        # Failed attempts consume the cap too; never fetch replacements.
                        unavailable.append(
                            UnavailableSource(
                                search_run_id=source.search_run_id,
                                fetch_run_id=uuid5(generation, step),
                                source_id=source.source.source_id,
                                code=error.code,
                            )
                        )
                await stage("grounding", unavailable=unavailable)
                context = GroundingContextBuilder(self.gateway).build(
                    request,
                    model,
                    capacity,
                    documents,
                    unavailable=bool(unavailable),
                    partial_search=any(s.result.partial or s.result.warnings for s in searches),
                )
                await stage(
                    "generating",
                    sources=context.sources,
                    context_tokens=context.context_tokens,
                    limitations=context.limitations,
                )
                await fence()
                prepared = True
                return context.request.model_copy(update={"research_deadline_at": deadline})
        except (ValidationError, ValueError):
            raise LLMError("RESEARCH_INVALID", 422) from None
        except TimeoutError:
            raise LLMError("TIMEOUT", 504) from None
        except ToolError as error:
            check_cancel()
            if error.code == "TOOL_CANCELLED":
                raise asyncio.CancelledError from None
            raise LLMError(
                "BUDGET_LIMIT"
                if error.code == "BUDGET_LIMIT"
                else "TIMEOUT"
                if error.code == "TOOL_TIMEOUT"
                else "RESEARCH_UNAVAILABLE",
                429 if error.code == "BUDGET_LIMIT" else 503,
            ) from None
        finally:
            if admitted and not prepared:
                await self.gateway.abandon(request.generationId)
            # The manager commits the answer and projection terminal atomically.
            if not admitted and projection is not None:
                await self.chat.update_research(
                    owner,
                    projection.model_copy(update={"state": "failed"}),
                    projection.state,
                    finalizing=True,
                )
