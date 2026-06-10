from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    email: str = Field(default="", max_length=160)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("username", "email", mode="before")
    @classmethod
    def strip_text_fields(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class LoginRequest(BaseModel):
    login: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("login", mode="before")
    @classmethod
    def strip_login(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class UserRead(BaseModel):
    id: int
    username: str
    email: str | None
    role: str
    status: str


class AuthResponse(BaseModel):
    token: str
    user: UserRead


class SetupStatusResponse(BaseModel):
    setup_required: bool
