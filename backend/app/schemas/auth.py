from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    email: str = Field(default="", max_length=160)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    login: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=6, max_length=128)


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
