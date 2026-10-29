from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from .models import Status


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=48)
    password: str = Field(min_length=10, max_length=128)
    invite_code: str = Field(min_length=4, max_length=64)


class LoginIn(BaseModel):
    login: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    dkl_number: str
    username: str
    display_name: str
    status: Status
    status_message: str
    theme: str
    model_config = {"from_attributes": True}


class ProfilePatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=48)
    status: Status | None = None
    status_message: str | None = Field(default=None, max_length=120)
    theme: str | None = Field(default=None, pattern=r"^(classic-blue|classic-green|xp-silver|dark-retro)$")


class FriendRequestIn(BaseModel):
    dkl_number: str = Field(pattern=r"^\d{8}$")


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body")
    @classmethod
    def non_blank(cls, value: str):
        if not value.strip():
            raise ValueError("Nachricht darf nicht leer sein")
        return value


class MessageOut(BaseModel):
    id: int
    sender_id: int
    recipient_id: int
    body: str
    created_at: datetime
    edited_at: datetime | None
    deleted: bool
    model_config = {"from_attributes": True}

