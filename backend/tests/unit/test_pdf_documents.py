import json
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from noris_ai.chat.attachment_content import ExtractionError
from noris_ai.chat.attachment_parser import extract
from noris_ai.chat.attachments import AttachmentService
from noris_ai.chat.errors import ChatError
from noris_ai.chat.models import ChatAttachment, ChatMessage
from noris_ai.chat.pdf_context import pdf_request
from noris_ai.chat.schemas import MessageRole
from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.schemas import ChatRequest, LLMMessage
from tests.fixtures.attachments import large_pdf, large_pdf_texts, synthetic_pdf


async def test_reported_pdf_is_fully_extracted_in_the_isolated_parser(
    tmp_path: Path, llm_config: Settings
) -> None:
    data = large_pdf()
    assert len(data) == 995_537 and data.startswith(b"%PDF-1.5")
    path = tmp_path / "large.pdf"
    path.write_bytes(data)
    engine = create_async_engine(llm_config.database_url.get_secret_value())
    try:
        service = AttachmentService(llm_config, async_sessionmaker(engine))
        value = await service.parse(path, "application/pdf")
    finally:
        await engine.dispose()
    assert value.has_text and value.text is None and value.page_count == 29
    assert [section.page for section in value.sections] == list(range(1, 30))
    assert [section.text for section in value.sections] == large_pdf_texts()
    assert sum(len(section.text) for section in value.sections) == 43_313
    assert path.read_bytes() == data


def test_long_single_page_is_split_without_losing_characters(tmp_path: Path) -> None:
    text = "a" * 1999 + " " + "b" * 2000 + " " + "last paragraph"
    path = tmp_path / "page.pdf"
    path.write_bytes(synthetic_pdf(text=text))
    value = extract(path, "application/pdf", 20_000, 100, 1000)
    assert len(value.sections) == 3
    assert {section.page for section in value.sections} == {1}
    assert "".join(section.text for section in value.sections) == text


async def test_compressed_pdf_cannot_bypass_decompression_limits(
    tmp_path: Path, llm_config: Settings
) -> None:
    path = tmp_path / "compressed.pdf"
    path.write_bytes(synthetic_pdf(text="x" * 8_388_609, compressed=True))
    assert path.stat().st_size < llm_config.chat_attachment_max_file_bytes
    engine = create_async_engine(llm_config.database_url.get_secret_value())
    try:
        service = AttachmentService(llm_config, async_sessionmaker(engine))
        with pytest.raises(ChatError) as error:
            await service.parse(path, "application/pdf")
        assert error.value.code == "ATTACHMENT_PROCESSING_LIMIT"
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    "field,value",
    [
        ("chat_attachment_max_pdf_pages", 101),
        ("chat_attachment_max_pdf_text_chars", 1_000_001),
        ("chat_attachment_max_text_chars", 32_001),
    ],
)
def test_pdf_hard_limits_remain_enforced(llm_config: Settings, field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(**(llm_config.model_dump() | {field: value}))


@pytest.mark.parametrize(
    "data,text_limit,page_limit,code",
    [
        (synthetic_pdf(encrypted=True), 500_000, 100, "ATTACHMENT_PDF_ENCRYPTED"),
        (synthetic_pdf(pages=2), 500_000, 1, "ATTACHMENT_PDF_PAGE_LIMIT"),
        (synthetic_pdf(text="x" * 101), 100, 100, "ATTACHMENT_TEXT_LIMIT"),
    ],
)
def test_pdf_limits_have_distinct_safe_errors(
    tmp_path: Path, data: bytes, text_limit: int, page_limit: int, code: str
) -> None:
    path = tmp_path / "bounded.pdf"
    path.write_bytes(data)
    with pytest.raises(ExtractionError) as error:
        extract(path, "application/pdf", text_limit, page_limit, 1000)
    assert error.value.code == code


async def test_pdf_error_codes_survive_the_parser_boundary(
    tmp_path: Path, llm_config: Settings
) -> None:
    path = tmp_path / "encrypted.pdf"
    path.write_bytes(synthetic_pdf(encrypted=True))
    engine = create_async_engine(llm_config.database_url.get_secret_value())
    try:
        service = AttachmentService(llm_config, async_sessionmaker(engine))
        with pytest.raises(ChatError) as error:
            await service.parse(path, "application/pdf")
        assert error.value.code == "ATTACHMENT_PDF_ENCRYPTED"
        assert "fixture-password" not in str(error.value)
    finally:
        await engine.dispose()


def document_message() -> ChatMessage:
    attachment = ChatAttachment(
        id=uuid4(),
        original_filename="large.pdf",
        mime_type="application/pdf",
        status="ready",
        pdf_page_count=29,
        pdf_sections=[
            {"page": page, "text": text} for page, text in enumerate(large_pdf_texts(), start=1)
        ],
    )
    return ChatMessage(role="user", content="Welche Schlussklausel gilt?", attachments=[attachment])


def request_for(path: list[ChatMessage]) -> ChatRequest:
    return ChatRequest(
        generationId="pdf-generation",
        conversationId="pdf-conversation",
        inputMessageId="input",
        modelId="fixture-alpha",
        attempt=1,
        messages=[
            LLMMessage(role=cast(MessageRole, message.role), content=message.content)
            for message in path
        ],
    )


def pdf_files(request: ChatRequest, index: int = 0) -> list[dict[str, object]]:
    return json.loads(request.messages[index].content.split("\n")[-1])


def selected_sections(request: ChatRequest) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], pdf_files(request)[0]["sections"])


def test_relevant_last_page_is_selected_and_storage_is_unchanged(llm_config: Settings) -> None:
    message = document_message()
    gateway = LLMGateway(llm_config, None)
    model = llm_config.llm_models[0]
    request = request_for([message])
    selected = pdf_request(
        request, [message], llm_config, lambda value: gateway.check_input(value, model)
    )
    sections = selected_sections(selected)
    assert len(sections) == 1 and sections[0]["page"] == 29
    assert "98765" in selected.messages[0].content
    assert "Anfangsklausel" not in selected.messages[0].content
    assert pdf_files(selected)[0]["selection"] == "excerpts"
    assert "[Dateiname, Seite N]" in selected.messages[0].content
    assert "untrusted input" in selected.messages[0].content
    assert request.messages[0].content == message.content
    assert len(message.attachments[0].pdf_sections or []) == 29


@pytest.mark.parametrize("context_window", [5000, 8192])
def test_broad_questions_fit_the_selected_model_and_keep_whole_sections(
    llm_config: Settings, context_window: int
) -> None:
    message = document_message()
    message.content = "Fasse das PDF zusammen"
    gateway = LLMGateway(llm_config, None)
    model = llm_config.llm_models[0].model_copy(update={"context_window": context_window})
    request = request_for([message])
    selected = pdf_request(
        request, [message], llm_config, lambda value: gateway.check_input(value, model)
    )
    gateway.check_input(selected, model)
    sections = selected_sections(selected)
    assert 0 < len(sections) < 29
    originals = large_pdf_texts()
    for section in sections:
        assert section["text"] == originals[cast(int, section["page"]) - 1]
    assert pdf_files(selected)[0]["selection"] == "excerpts"
    assert "keine vollständige Dokumentanalyse" in selected.messages[0].content


def test_followup_reselects_an_earlier_attachment_and_honors_page_ranges(
    llm_config: Settings,
) -> None:
    first = document_message()
    path = [
        first,
        ChatMessage(role="assistant", content="Antwort mit Seite 29."),
        ChatMessage(role="user", content="Was steht auf Seiten 1-2?", attachments=[]),
    ]
    request = request_for(path)
    gateway = LLMGateway(llm_config, None)
    model = llm_config.llm_models[0]
    selected = pdf_request(
        request, path, llm_config, lambda value: gateway.check_input(value, model)
    )
    sections = selected_sections(selected)
    assert {section["page"] for section in sections} == {1, 2}
    assert selected.messages[1:] == request.messages[1:]


def test_short_pdf_uses_complete_context(llm_config: Settings) -> None:
    message = document_message()
    message.attachments[0].pdf_sections = [{"page": 1, "text": "Short complete text"}]
    message.attachments[0].pdf_page_count = 1
    gateway = LLMGateway(llm_config, None)
    selected = pdf_request(
        request_for([message]),
        [message],
        llm_config,
        lambda value: gateway.check_input(value, llm_config.llm_models[0]),
    )
    assert pdf_files(selected)[0]["selection"] == "complete"


def test_pdf_selection_respects_request_bytes_as_well_as_tokens(llm_config: Settings) -> None:
    message = document_message()
    message.content = "Fasse das PDF zusammen"
    config = llm_config.model_copy(update={"llm_max_request_bytes": 3200})
    gateway = LLMGateway(config, None)
    selected = pdf_request(
        request_for([message]),
        [message],
        config,
        lambda value: gateway.check_input(value, config.llm_models[0]),
    )
    assert len(selected_sections(selected)) == 1
    gateway.check_input(selected, config.llm_models[0])


def test_multiple_pdfs_select_the_relevant_document(llm_config: Settings) -> None:
    message = document_message()
    second = document_message().attachments[0]
    second.original_filename = "other.pdf"
    second.pdf_sections = [{"page": 29, "text": "Auszahlung erfolgt am Monatsende."}]
    message.attachments.append(second)
    message.content = "Wann erfolgt die Auszahlung?"
    gateway = LLMGateway(llm_config, None)
    selected = pdf_request(
        request_for([message]),
        [message],
        llm_config,
        lambda value: gateway.check_input(value, llm_config.llm_models[0]),
    )
    files = pdf_files(selected)
    assert files[0]["sections"] == []
    assert files[1]["filename"] == "other.pdf"
    assert "Monatsende" in selected.messages[0].content
    assert "98765" not in selected.messages[0].content


def test_history_that_fills_context_is_rejected_without_being_cut(llm_config: Settings) -> None:
    message = document_message()
    message.content = "x" * 8000
    request = request_for([message])
    gateway = LLMGateway(llm_config, None)
    with pytest.raises(LLMError) as error:
        pdf_request(
            request,
            [message],
            llm_config,
            lambda value: gateway.check_input(value, llm_config.llm_models[0]),
        )
    assert error.value.code == "CONTEXT_LIMIT"
    assert request.messages[0].content == "x" * 8000
