from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class AccountResponse(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    role: Literal["admin", "technician"]
    is_active: bool


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["admin", "technician"] | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self):
        if self.role is None and self.is_active is None:
            raise ValueError("Indica role o is_active.")
        return self
