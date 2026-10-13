"""Contract tests; no paid requests, network or real GPU required."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from noris_ai.image_generation.provider import ImageCapabilities, ImageInput, ImageOutput


def test_unverified_image_model_cannot_be_admitted() -> None:
    model = ImageCapabilities(provider_id="test", model_id="example", sizes=("1024x1024",), formats=("png",))
    assert not model.ready_for_admission


def test_verified_model_requires_price_evidence() -> None:
    model = ImageCapabilities(
        provider_id="test", model_id="example", evidence="verified",
        sizes=("1024x1024",), formats=("png",),
        price_upper_bound_usd=Decimal("0.05"), price_source="operator-confirmed",
    )
    assert model.ready_for_admission


@pytest.mark.parametrize("prompt", ["", "  ", "\n\t"])
def test_empty_prompt_rejected(prompt: str) -> None:
    with pytest.raises(ValidationError):
        ImageInput(prompt=prompt, model_id="example", size="1024x1024")


def test_unknown_provider_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ImageInput.model_validate({"prompt": "A lighthouse", "model_id": "example", "size": "1024x1024", "remote_url": "https://example.com"})


def test_result_has_bounded_bytes_and_no_remote_url() -> None:
    result = ImageOutput(content=b"sample", mime_type="image/png", model_id="example")
    assert result.measured_cost_usd is None
    with pytest.raises(ValidationError):
        ImageOutput(content=b"", mime_type="image/png", model_id="example")
