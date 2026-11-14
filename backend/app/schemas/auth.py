from pydantic import BaseModel, ConfigDict


class AuthUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    email: str
    email_verified: bool
    name: str | None = None
    picture: str | None = None


class SessionResponse(BaseModel):
    authenticated: bool
    user: AuthUser | None = None
    access_token: str | None = None
    token_type: str | None = None
    expires_in: int | None = None

