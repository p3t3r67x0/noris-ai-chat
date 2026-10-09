"""REST resources for persisted conversations (Etappe 3).

Durable resource operations live here; live streaming, generation commands
and resume run over the WebSocket endpoint. Both share the same repository
and service layer.
"""

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBasicCredentials

from noris_ai.chat.errors import ChatError
from noris_ai.chat.generation import GenerationManager
from noris_ai.chat.repository import UNCHANGED
from noris_ai.chat.schemas import (
    ChatImportRequest,
    ChatImportResponse,
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
    DraftListResponse,
    DraftResponse,
    DraftUpdate,
    MessageListResponse,
    PreferencesResponse,
    PreferencesUpdate,
)
from noris_ai.chat.service import ChatService
from noris_ai.core.access import security, verify_basic, verify_write_origin
from noris_ai.core.config import Settings
from noris_ai.core.schemas import ErrorResponse

router = APIRouter(tags=["Chat"])


async def chat_access(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(security)],
) -> tuple[ChatService, UUID]:
    config = cast(Settings, request.app.state.chat_settings)
    verify_basic(credentials, config)
    verify_write_origin(request, config)
    return cast(ChatService, request.app.state.chat_service), config.chat_owner_id


ChatAccess = Annotated[tuple[ChatService, UUID], Depends(chat_access)]


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorResponse} for code in (400, 401, 403, 404, 409, 413, 422, 500, 503)
}


@router.get(
    "/conversations",
    operation_id="listConversations",
    response_model=ConversationListResponse,
    responses=ERROR_RESPONSES,
)
async def list_conversations(
    access: ChatAccess,
    archived: bool = False,
) -> ConversationListResponse:
    service, owner_id = access
    return ConversationListResponse(
        conversations=await service.list_conversations(owner_id, include_archived=archived)
    )


@router.post(
    "/conversations",
    operation_id="createConversation",
    response_model=ConversationResponse,
    status_code=201,
    responses=ERROR_RESPONSES,
)
async def create_conversation(
    payload: ConversationCreate,
    access: ChatAccess,
) -> ConversationResponse:
    service, owner_id = access
    return await service.create_conversation(owner_id, payload.title, payload.id)


@router.get(
    "/conversations/{conversation_id}",
    operation_id="getConversation",
    response_model=ConversationResponse,
    responses=ERROR_RESPONSES,
)
async def get_conversation(
    conversation_id: UUID,
    access: ChatAccess,
) -> ConversationResponse:
    service, owner_id = access
    return await service.get_conversation(owner_id, conversation_id)


@router.patch(
    "/conversations/{conversation_id}",
    operation_id="updateConversation",
    response_model=ConversationResponse,
    responses=ERROR_RESPONSES,
)
async def update_conversation(
    conversation_id: UUID,
    payload: ConversationUpdate,
    access: ChatAccess,
) -> ConversationResponse:
    service, owner_id = access
    fields = payload.model_fields_set
    if len(fields - {"version"}) != 1:
        raise ChatError("INVALID_INPUT", 422)
    if "title" in fields and payload.title is not None:
        return await service.rename_conversation(
            owner_id, conversation_id, payload.title, payload.version
        )
    if "archived" in fields and payload.archived is not None:
        return await service.set_archived(
            owner_id, conversation_id, payload.archived, payload.version
        )
    if "activeLeafMessageId" in fields and payload.activeLeafMessageId is not None:
        return await service.set_active_leaf(
            owner_id, conversation_id, payload.activeLeafMessageId, payload.version
        )
    raise ChatError("INVALID_INPUT", 422)


@router.delete(
    "/conversations/{conversation_id}",
    operation_id="deleteConversation",
    status_code=204,
    responses=ERROR_RESPONSES,
)
async def delete_conversation(
    conversation_id: UUID,
    access: ChatAccess,
    request: Request,
) -> None:
    service, owner_id = access
    await cast(GenerationManager, request.app.state.chat_generations).cancel_conversation(
        conversation_id
    )
    await service.delete_conversation(owner_id, conversation_id)


@router.get(
    "/conversations/{conversation_id}/messages",
    operation_id="listConversationMessages",
    response_model=MessageListResponse,
    responses=ERROR_RESPONSES,
)
async def list_conversation_messages(
    conversation_id: UUID,
    access: ChatAccess,
) -> MessageListResponse:
    service, owner_id = access
    return MessageListResponse(messages=await service.list_messages(owner_id, conversation_id))


@router.put(
    "/conversations/{conversation_id}/draft",
    operation_id="upsertConversationDraft",
    response_model=DraftResponse,
    responses=ERROR_RESPONSES,
)
async def upsert_draft(
    conversation_id: UUID,
    payload: DraftUpdate,
    access: ChatAccess,
) -> DraftResponse:
    service, owner_id = access
    await service.get_conversation(owner_id, conversation_id)
    return await service.set_draft(owner_id, str(conversation_id), payload.content)


@router.get(
    "/chat/drafts",
    operation_id="listChatDrafts",
    response_model=DraftListResponse,
    responses=ERROR_RESPONSES,
)
async def list_drafts(
    access: ChatAccess,
) -> DraftListResponse:
    service, owner_id = access
    return DraftListResponse(drafts=await service.list_drafts(owner_id))


@router.put("/chat/drafts/new", operation_id="upsertNewChatDraft", response_model=DraftResponse)
async def upsert_new_draft(payload: DraftUpdate, access: ChatAccess) -> DraftResponse:
    service, owner_id = access
    return await service.set_draft(owner_id, "__new__", payload.content)


@router.get(
    "/chat/preferences",
    operation_id="getChatPreferences",
    response_model=PreferencesResponse,
    responses=ERROR_RESPONSES,
)
async def get_preferences(
    access: ChatAccess,
) -> PreferencesResponse:
    service, owner_id = access
    return await service.get_preferences(owner_id)


@router.put(
    "/chat/preferences",
    operation_id="updateChatPreferences",
    response_model=PreferencesResponse,
    responses=ERROR_RESPONSES,
)
async def update_preferences(
    payload: PreferencesUpdate,
    access: ChatAccess,
) -> PreferencesResponse:
    service, owner_id = access
    fields = payload.model_fields_set
    active = payload.activeConversationId if "activeConversationId" in fields else UNCHANGED
    model = payload.modelId if "modelId" in fields else UNCHANGED
    return await service.set_preferences(owner_id, active, model)


@router.post(
    "/conversations/import",
    operation_id="importChatSnapshot",
    response_model=ChatImportResponse,
    responses=ERROR_RESPONSES,
)
async def import_snapshot(
    payload: ChatImportRequest,
    access: ChatAccess,
) -> ChatImportResponse:
    service, owner_id = access
    return await service.import_snapshot(owner_id, payload)
