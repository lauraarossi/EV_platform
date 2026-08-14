from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    display_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleCallbackRequest(BaseModel):
    """The credential returned by Google Identity Services in the browser."""

    credential: str


class UserRead(BaseModel):
    id: int
    email: str
    display_name: str | None
    avatar_url: str | None
    has_password: bool
    # True when the account is linked to Google, so the UI can explain how to
    # sign in next time.
    has_google: bool

    model_config = {"from_attributes": True}


class AuthOptions(BaseModel):
    """What the sign-in page should offer."""

    google_enabled: bool
    registration_open: bool
    google_client_id: str | None
