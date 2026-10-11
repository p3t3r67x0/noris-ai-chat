"""Authenticated raw file upload. One bounded stream per selected file."""

import base64
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse, Response

from noris_ai.api.v1.conversations import ERROR_RESPONSES, ChatAccess
from noris_ai.chat.attachments import MIME_EXTENSIONS, AttachmentService
from noris_ai.chat.errors import ChatError
from noris_ai.chat.schemas import (
    AttachmentLimitsResponse,
    AttachmentListResponse,
    AttachmentResponse,
)
from noris_ai.core.config import Settings

router = APIRouter(prefix="/chat/attachments", tags=["Chat attachments"])


def service(request: Request) -> AttachmentService:
    return cast(AttachmentService, request.app.state.chat_attachments)


@router.get(
    "/limits",
    operation_id="getAttachmentLimits",
    response_model=AttachmentLimitsResponse,
    responses=ERROR_RESPONSES,
)
async def limits(request: Request, access: ChatAccess) -> AttachmentLimitsResponse:
    config = cast(Settings, request.app.state.chat_settings)
    return AttachmentLimitsResponse(
        maxFileBytes=config.chat_attachment_max_file_bytes,
        maxFiles=config.chat_attachment_max_files,
        ownerQuotaBytes=config.chat_attachment_owner_quota_bytes,
        mimeTypes=list(MIME_EXTENSIONS),
    )


@router.post(
    "",
    operation_id="uploadChatAttachment",
    response_model=AttachmentResponse,
    status_code=201,
    responses=ERROR_RESPONSES,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                mime: {"schema": {"type": "string", "format": "binary"}} for mime in MIME_EXTENSIONS
            },
        }
    },
)
async def upload(
    request: Request,
    access: ChatAccess,
    conversationId: UUID,
    filename: Annotated[str, Query(min_length=1, max_length=200)],
) -> AttachmentResponse:
    _, owner = access
    length = request.headers.get("content-length")
    config = cast(Settings, request.app.state.chat_settings)
    if length and (not length.isdecimal() or int(length) > config.chat_attachment_max_file_bytes):
        raise ChatError("ATTACHMENT_SIZE", 413)
    mime = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    return await service(request).upload(owner, conversationId, filename, mime, request.stream())


@router.get(
    "",
    operation_id="listChatAttachments",
    response_model=AttachmentListResponse,
    responses=ERROR_RESPONSES,
)
async def list_attachments(
    request: Request, access: ChatAccess, conversationId: UUID
) -> AttachmentListResponse:
    _, owner = access
    return AttachmentListResponse(attachments=await service(request).list(owner, conversationId))


@router.delete(
    "/{attachment_id}",
    operation_id="deleteChatAttachment",
    status_code=204,
    responses=ERROR_RESPONSES,
)
async def remove(request: Request, access: ChatAccess, attachment_id: UUID) -> None:
    _, owner = access
    await service(request).remove(owner, attachment_id)


@router.get(
    "/{attachment_id}/content",
    operation_id="downloadChatAttachment",
    response_class=FileResponse,
    responses={
        **ERROR_RESPONSES,
        200: {
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}},
                "image/jpeg": {"schema": {"type": "string", "format": "binary"}},
            }
        },
    },
)
async def download(
    request: Request,
    access: ChatAccess,
    attachment_id: UUID,
    preview: Annotated[
        bool, Query(description="Normalisierte Vorschau für PNG/JPEG-Bilder")
    ] = False,
) -> Response:
    _, owner = access
    attachments = service(request)
    attachment = await attachments.get(owner, attachment_id)
    headers = {
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "sandbox; default-src 'none'",
    }
    if preview:
        if attachment.mime_type not in ("image/png", "image/jpeg"):
            raise ChatError("ATTACHMENT_TYPE", 415)
        image = await attachments.image_input(owner, attachment.conversation_id, attachment_id)
        return Response(
            content=base64.b64decode(image.data_url.split(",", 1)[1], validate=True),
            media_type="image/jpeg",
            headers=headers | {"Content-Disposition": "inline"},
        )
    path = attachments.path(attachment.storage_key)
    if path.is_symlink() or not path.is_file():
        raise ChatError("ATTACHMENT_NOT_FOUND", 404)
    return FileResponse(
        path,
        filename=attachment.original_filename,
        media_type="application/octet-stream",
        content_disposition_type="attachment",
        headers=headers,
    )
