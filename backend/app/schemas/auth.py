from pydantic import BaseModel


class LoginRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    token: str


class VerifyResponse(BaseModel):
    valid: bool
