from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    amount: float = Field(..., gt=0, description="Positive amount to charge")
    currency: str = Field(..., min_length=3, max_length=3,
                          description="ISO-4217 currency code, e.g. 'USD'")

    @field_validator("currency")
    @classmethod
    def _upper(cls, v: str) -> str:
        v = v.upper()
        if not v.isalpha():
            raise ValueError("currency must be 3 alphabetic characters")
        return v
