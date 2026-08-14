import datetime

from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """An account.

    Two ways in, both landing on the same record: an email and password, or
    Google. `password_hash` is null for accounts that only ever signed in with
    Google, and `google_sub` is null for password-only accounts. Someone who
    signs up with a password and later uses Google with the same verified email
    is linked to their existing account rather than getting a duplicate.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Stored lower-cased so sign-in is not case-sensitive.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(120))

    # Null when the account has only ever used Google.
    password_hash: Mapped[str | None] = mapped_column(String(200))

    # Google's stable subject id. Not the email, which a person can change.
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))

    vehicles: Mapped[list["Vehicle"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    tariffs: Mapped[list["ElectricityTariff"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None
