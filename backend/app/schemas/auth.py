from datetime import date

from pydantic import AliasChoices, BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    gender: str
    birth_date: date = Field(validation_alias=AliasChoices("birth_date", "birthdate"))
    phone: str
    address: str

    @field_validator("username", "gender", "phone", "address")
    @classmethod
    def require_non_blank_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("This field is required")
        return text


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    status: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
