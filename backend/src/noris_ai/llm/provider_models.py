"""Validated Noris catalog facts. Unknown additions are ignored at every level."""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

PositiveInt = Annotated[int, Field(strict=True, gt=0)]


class ProviderSchema(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)


class ProviderLength(ProviderSchema):
    value: PositiveInt | None = None
    unit: str | None = None


class ProviderParameter(ProviderSchema):
    type: str | None = None
    max: PositiveInt | None = None
    min: int | None = None
    unit: str | None = None


class ProviderInputs(ProviderSchema):
    max_context_length: ProviderLength | None = None


class ProviderPrice(ProviderSchema):
    type: str
    unit: str
    cost_usd: Decimal = Field(ge=0, allow_inf_nan=False)

    @field_validator("cost_usd", mode="before")
    @classmethod
    def decimal_price(cls, value: object) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
            raise ValueError("Invalid USD price")
        return Decimal(str(value))


class ProviderModality(ProviderSchema):
    type: str
    supported_inputs: ProviderInputs | None = None
    # Only consumed parameter contracts are typed; unrelated parameters are ignored.
    supported_parameters: dict[str, object] = Field(default_factory=dict)
    max_length: ProviderLength | None = None
    streaming: bool | None = None
    pricing: list[ProviderPrice] = Field(default_factory=list)

    def token_parameter(self, name: str) -> ProviderParameter | None:
        from pydantic import ValidationError

        value = self.supported_parameters.get(name)
        if value is None:
            return None
        try:
            return ProviderParameter.model_validate(value)
        except ValidationError:
            return None


class ProviderModel(ProviderSchema):
    schema_version: str | None = None
    id: str = Field(min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._/:-]*$")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    input_modalities: list[ProviderModality] | None = None
    output_modalities: list[ProviderModality] | None = None
    hugging_face_id: str | None = None
    created: int | None = Field(default=None, ge=0)
    is_ready: bool | None = None
    is_free: bool | None = None
    # Unit/semantics are not established: retain separately, never alter USD rates.
    discount_to_user: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)

    @field_validator("discount_to_user", mode="before")
    @classmethod
    def decimal_discount(cls, value: object) -> Decimal | None:
        return None if value is None else ProviderPrice.decimal_price(value)

    @property
    def compatible_version(self) -> bool:
        # Missing/older compatible metadata is still parsed; future major changes fail closed.
        return self.schema_version is None or self.schema_version.split(".")[0] == "2"


class ProviderModels(ProviderSchema):
    # Entry validation is isolated so one malformed model cannot grant access or hide others.
    data: list[object]
