"""Bounded uploads to private disk storage with PostgreSQL ownership and quotas."""

import asyncio
import hashlib
import json
import os
import re
import sys
from collections.abc import AsyncIterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import func, select

from noris_ai.chat.attachment_content import ExtractedAttachment
from noris_ai.chat.errors import ChatError
from noris_ai.chat.models import ChatAttachment, ChatConversation, ChatMessage
from noris_ai.chat.repository import ModelDatabase
from noris_ai.chat.schemas import AttachmentResponse, TextReferenceCreate
from noris_ai.chat.service import attachment_response
from noris_ai.core.config import Settings
from noris_ai.llm.vision import VisionImage

MIME_EXTENSIONS = {
    "text/plain": (".txt",),
    "text/markdown": (".md", ".markdown"),
    "application/pdf": (".pdf",),
    "image/png": (".png",),
    "image/jpeg": (".jpg", ".jpeg"),
}


def validate_filename(filename: str, mime: str) -> None:
    if (
        not filename
        or len(filename) > 200
        or filename in (".", "..")
        or any(c in filename for c in "/\\")
        or any(
            ord(c) < 32 or c in "\x7f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
            for c in filename
        )
        or mime not in MIME_EXTENSIONS
        or Path(filename).suffix.lower() not in MIME_EXTENSIONS[mime]
    ):
        raise ChatError("ATTACHMENT_TYPE", 415)


class AttachmentService:
    def __init__(self, config: Settings, database: ModelDatabase) -> None:
        self.config, self.database = config, database
        self.root = Path(config.chat_attachment_storage_dir).absolute()
        self.parsers = asyncio.Semaphore(2)

    def path(self, key: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", key):
            raise ChatError("ATTACHMENT_NOT_FOUND", 404)
        return self.root / key

    async def parse(self, path: Path, mime: str) -> ExtractedAttachment:
        result = await self._parse(path, mime)
        if "text" not in result:
            raise ChatError("ATTACHMENT_INVALID", 422)
        try:
            extracted = ExtractedAttachment.model_validate(result)
        except ValidationError:
            raise ChatError("ATTACHMENT_INVALID", 422) from None
        if mime == "application/pdf":
            if (
                extracted.text is not None
                or extracted.page_count is None
                or extracted.page_count > self.config.chat_attachment_max_pdf_pages
                or any(section.page > extracted.page_count for section in extracted.sections)
                or sum(len(section.text) for section in extracted.sections)
                > self.config.chat_attachment_max_pdf_text_chars
            ):
                raise ChatError("ATTACHMENT_INVALID", 422)
        elif (
            extracted.sections
            or extracted.page_count is not None
            or len(extracted.text or "") > self.config.chat_attachment_max_text_chars
        ):
            raise ChatError("ATTACHMENT_INVALID", 422)
        return extracted

    async def image_input(
        self, owner: UUID, conversation_id: UUID, attachment_id: UUID
    ) -> VisionImage:
        attachment = await self.get(owner, attachment_id)
        if (
            attachment.conversation_id != conversation_id
            or attachment.status != "stored"
            or attachment.mime_type not in ("image/png", "image/jpeg")
            or attachment.extracted_text
        ):
            raise ChatError("ATTACHMENT_INCOMPATIBLE", 422)
        result = await self._parse(
            self.path(attachment.storage_key),
            attachment.mime_type,
            "vision",
            str(attachment.size_bytes),
            attachment.sha256,
        )
        return VisionImage.model_validate(result)

    async def _parse(self, path: Path, mime: str, *extra: str) -> dict[str, object]:
        async with self.parsers:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "noris_ai.chat.attachment_parser",
                str(path),
                mime,
                str(
                    self.config.chat_attachment_max_pdf_text_chars
                    if mime == "application/pdf"
                    else self.config.chat_attachment_max_text_chars
                ),
                str(self.config.chat_attachment_max_pdf_pages),
                str(self.config.chat_attachment_max_image_pixels),
                *extra,
                # No inherited environment: provider keys cannot enter the parser.
                env={"LANG": "C.UTF-8"},
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                output_limit = (
                    750_000
                    if extra
                    else 6 * self.config.chat_attachment_max_pdf_text_chars + 65_536
                    if mime == "application/pdf"
                    else 200_000
                )
                async with asyncio.timeout(15):
                    if process.stdout is None:
                        raise ChatError("ATTACHMENT_INVALID", 422)
                    stdout = bytearray()
                    while chunk := await process.stdout.read(65_536):
                        stdout.extend(chunk)
                        if len(stdout) > output_limit:
                            raise ChatError("ATTACHMENT_PROCESSING_LIMIT", 422)
                    await process.wait()
                if process.returncode is not None and process.returncode < 0:
                    raise ChatError("ATTACHMENT_PROCESSING_LIMIT", 422)
                if process.returncode != 0:
                    raise ChatError("ATTACHMENT_INVALID", 422)
                result: object = json.loads(stdout)
                if not isinstance(result, dict):
                    raise ChatError("ATTACHMENT_INVALID", 422)
                parsed = cast(dict[str, object], result)
                code = parsed.get("error")
                if isinstance(code, str) and code in {
                    "ATTACHMENT_PDF_ENCRYPTED",
                    "ATTACHMENT_PDF_PAGE_LIMIT",
                    "ATTACHMENT_TEXT_LIMIT",
                    "ATTACHMENT_PROCESSING_LIMIT",
                }:
                    raise ChatError(code, 422)
                return parsed
            except TimeoutError:
                raise ChatError("ATTACHMENT_PROCESSING_TIMEOUT", 422) from None
            except (ValueError, UnicodeError):
                raise ChatError("ATTACHMENT_INVALID", 422) from None
            finally:
                if process.returncode is None:
                    process.kill()
                await process.wait()

    async def upload(
        self,
        owner: UUID,
        conversation_id: UUID,
        filename: str,
        mime: str,
        chunks: AsyncIterable[bytes],
    ) -> AttachmentResponse:
        validate_filename(filename, mime)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.root.is_symlink():
            raise ChatError("INTERNAL_ERROR", 500)
        key = uuid4().hex
        path = self.path(key)
        committed = False
        try:
            async with self.database() as session, session.begin():
                # The owner lock serializes quota accounting across conversations/processes.
                await session.execute(select(func.pg_advisory_xact_lock(owner.int % (2**63))))
                conversation = await session.scalar(
                    select(ChatConversation)
                    .where(
                        ChatConversation.id == conversation_id,
                        ChatConversation.owner_id == owner,
                        ChatConversation.deleted_at.is_(None),
                        ChatConversation.archived_at.is_(None),
                    )
                    .with_for_update()
                )
                if conversation is None:
                    raise ChatError("NOT_FOUND", 404)
                active = (
                    await session.scalars(
                        select(ChatAttachment).where(
                            ChatAttachment.owner_id == owner,
                            ChatAttachment.status != "deleted",
                        )
                    )
                ).all()
                used = sum(a.size_bytes for a in active)
                pending = sum(
                    a.conversation_id == conversation_id and a.message_id is None for a in active
                )
                if len(active) >= 200 or pending >= self.config.chat_attachment_max_files:
                    raise ChatError("ATTACHMENT_QUOTA", 413)
                size = 0
                digest = hashlib.sha256()
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "wb") as target:
                    async with asyncio.timeout(60):
                        async for chunk in chunks:
                            size += len(chunk)
                            if size > self.config.chat_attachment_max_file_bytes:
                                raise ChatError("ATTACHMENT_SIZE", 413)
                            if used + size > self.config.chat_attachment_owner_quota_bytes:
                                raise ChatError("ATTACHMENT_QUOTA", 413)
                            digest.update(chunk)
                            await asyncio.to_thread(target.write, chunk)
                    await asyncio.to_thread(target.flush)
                    await asyncio.to_thread(os.fsync, target.fileno())
                if not size:
                    raise ChatError("ATTACHMENT_SIZE", 413)
                extracted = await self.parse(path, mime)
                attachment = ChatAttachment(
                    id=uuid4(),
                    owner_id=owner,
                    conversation_id=conversation_id,
                    original_filename=filename,
                    storage_key=key,
                    mime_type=mime,
                    size_bytes=size,
                    sha256=digest.hexdigest(),
                    status="ready" if extracted.has_text else "stored",
                    extracted_text=extracted.text,
                    pdf_sections=[section.model_dump() for section in extracted.sections]
                    if mime == "application/pdf"
                    else None,
                    pdf_page_count=extracted.page_count,
                )
                session.add(attachment)
                await session.flush()
                response = attachment_response(attachment)
            committed = True
            return response
        except TimeoutError:
            raise ChatError("ATTACHMENT_UPLOAD_TIMEOUT", 408) from None
        finally:
            if not committed:
                path.unlink(missing_ok=True)

    async def list(self, owner: UUID, conversation_id: UUID) -> list[AttachmentResponse]:
        async with self.database() as session:
            conversation = await session.scalar(
                select(ChatConversation).where(
                    ChatConversation.id == conversation_id,
                    ChatConversation.owner_id == owner,
                    ChatConversation.deleted_at.is_(None),
                )
            )
            if conversation is None:
                raise ChatError("NOT_FOUND", 404)
            rows = await session.scalars(
                select(ChatAttachment)
                .where(
                    ChatAttachment.owner_id == owner,
                    ChatAttachment.conversation_id == conversation_id,
                    ChatAttachment.status != "deleted",
                )
                .order_by(ChatAttachment.created_at, ChatAttachment.id)
                .limit(200)
            )
            return [attachment_response(a) for a in rows]

    async def reference(self, owner: UUID, value: TextReferenceCreate) -> AttachmentResponse:
        # Browser-selected rendered Markdown is user content, not an assertion of
        # the source's authority. Preserve its exact whitespace, without parsing it.
        try:
            data = value.text.encode("utf-8")
        except UnicodeEncodeError:
            raise ChatError("ATTACHMENT_INVALID", 422) from None
        if not value.text.strip() or len(value.text) > self.config.chat_attachment_max_text_chars:
            raise ChatError("ATTACHMENT_INVALID", 422)
        if len(data) > self.config.chat_attachment_max_file_bytes:
            raise ChatError("ATTACHMENT_SIZE", 413)
        async with self.database() as session, session.begin():
            await session.execute(select(func.pg_advisory_xact_lock(owner.int % (2**63))))
            target = await session.scalar(
                select(ChatConversation)
                .where(
                    ChatConversation.id == value.conversationId,
                    ChatConversation.owner_id == owner,
                    ChatConversation.deleted_at.is_(None),
                    ChatConversation.archived_at.is_(None),
                )
                .with_for_update()
            )
            source = await session.scalar(
                select(ChatMessage)
                .join(ChatConversation, ChatMessage.conversation_id == ChatConversation.id)
                .where(
                    ChatMessage.id == value.sourceMessageId,
                    ChatMessage.conversation_id == value.sourceConversationId,
                    ChatConversation.owner_id == owner,
                    ChatConversation.deleted_at.is_(None),
                )
            )
            if target is None or source is None:
                raise ChatError("NOT_FOUND", 404)
            active = (
                await session.scalars(
                    select(ChatAttachment).where(
                        ChatAttachment.owner_id == owner,
                        ChatAttachment.status != "deleted",
                    )
                )
            ).all()
            if (
                len(active) >= 200
                or sum(a.conversation_id == target.id and a.message_id is None for a in active)
                >= self.config.chat_attachment_max_files
                or sum(a.size_bytes for a in active) + len(data)
                > self.config.chat_attachment_owner_quota_bytes
            ):
                raise ChatError("ATTACHMENT_QUOTA", 413)
            attachment = ChatAttachment(
                id=uuid4(),
                owner_id=owner,
                conversation_id=target.id,
                original_filename="Markierter Text",
                storage_key=uuid4().hex,
                mime_type="text/plain",
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                status="ready",
                extracted_text=value.text,
                source_message_id=source.id,
                source_conversation_id=source.conversation_id,
            )
            session.add(attachment)
            await session.flush()
            return attachment_response(attachment)

    async def get(self, owner: UUID, attachment_id: UUID) -> ChatAttachment:
        async with self.database() as session:
            attachment = await session.scalar(
                select(ChatAttachment)
                .join(ChatConversation)
                .where(
                    ChatAttachment.id == attachment_id,
                    ChatAttachment.owner_id == owner,
                    ChatConversation.owner_id == owner,
                    ChatConversation.deleted_at.is_(None),
                    ChatAttachment.status != "deleted",
                )
            )
            if attachment is None:
                raise ChatError("ATTACHMENT_NOT_FOUND", 404)
            return attachment

    async def remove(self, owner: UUID, attachment_id: UUID) -> None:
        async with self.database() as session, session.begin():
            await session.execute(select(func.pg_advisory_xact_lock(owner.int % (2**63))))
            attachment = await session.scalar(
                select(ChatAttachment)
                .where(
                    ChatAttachment.id == attachment_id,
                    ChatAttachment.owner_id == owner,
                    ChatAttachment.status != "deleted",
                )
                .with_for_update()
            )
            if attachment is None:
                raise ChatError("ATTACHMENT_NOT_FOUND", 404)
            if attachment.message_id is not None:
                raise ChatError("ATTACHMENT_IN_USE", 409)
            self.path(attachment.storage_key).unlink(missing_ok=True)
            attachment.status, attachment.extracted_text = "deleted", None
            attachment.pdf_sections = None

    async def cleanup(self) -> None:
        cutoff = datetime.now(UTC) - timedelta(hours=self.config.chat_attachment_orphan_hours)
        async with self.database() as session, session.begin():
            await session.execute(
                select(func.pg_advisory_xact_lock(self.config.chat_owner_id.int % (2**63)))
            )
            rows = (
                await session.scalars(
                    select(ChatAttachment)
                    .join(ChatConversation)
                    .where(
                        ChatAttachment.owner_id == self.config.chat_owner_id,
                        (ChatConversation.deleted_at.is_not(None))
                        | (
                            ChatAttachment.message_id.is_(None)
                            & (ChatAttachment.created_at < cutoff)
                        )
                        | (ChatAttachment.status == "deleted"),
                    )
                    .with_for_update(of=ChatAttachment)
                )
            ).all()
            for attachment in rows:
                self.path(attachment.storage_key).unlink(missing_ok=True)
                attachment.status, attachment.extracted_text = "deleted", None
                attachment.pdf_sections = None
            known = set((await session.scalars(select(ChatAttachment.storage_key))).all())
            if self.root.exists():
                for path in self.root.iterdir():
                    if (
                        re.fullmatch(r"[0-9a-f]{32}", path.name)
                        and path.name not in known
                        and path.lstat().st_mtime < cutoff.timestamp()
                    ):
                        path.unlink(missing_ok=True)
