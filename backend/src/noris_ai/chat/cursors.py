"""Bounded, canonical, scope-bound seek cursors. Never contain SQL."""

import base64
import binascii
import json
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from noris_ai.chat.errors import ChatError


class Cursor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: int = Field(default=1, ge=1, le=1)
    scope: str = Field(max_length=500)
    id: UUID
    timestamp: datetime | None = None
    leaf: UUID | None = None
    revision: int | None = Field(default=None, ge=1)

    @field_validator("timestamp")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Timezone required")
        return value

    def encode(self) -> str:
        return base64.urlsafe_b64encode(self.model_dump_json().encode()).decode().rstrip("=")

    @classmethod
    def decode(cls, value: str, scope: str) -> "Cursor":
        try:
            if not value or len(value) > 2048:
                raise ValueError("Cursor length")
            raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
            result = cls.model_validate_json(raw)
            if result.encode() != value or result.scope != scope:
                raise ValueError("Cursor scope or encoding")
            return result
        except (ValueError, ValidationError, binascii.Error, json.JSONDecodeError) as error:
            raise ChatError("INVALID_CURSOR", 422) from error
