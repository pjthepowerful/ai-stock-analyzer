from typing import Optional

from pydantic import BaseModel


class SignupRequest(BaseModel):
    username: str
    password: str
    email: str


class LoginRequest(BaseModel):
    email: str
    password: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str
    purpose: str = "2fa"  # "2fa" | "verify"


class ResendCodeRequest(BaseModel):
    email: str
    purpose: str = "2fa"


class UserOut(BaseModel):
    id: int
    username: str
    email: str


class AuthResult(BaseModel):
    ok: bool = True
    token: Optional[str] = None
    user: Optional[UserOut] = None
    needs_verification: bool = False
    needs_2fa: bool = False
    twofa_skipped: bool = False
