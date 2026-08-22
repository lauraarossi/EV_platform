import datetime
import enum

from sqlalchemy import String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FeedbackStatus(str, enum.Enum):
    new = "new"
    read = "read"
    done = "done"


class Feedback(Base):
    """Something someone took the trouble to say.

    Kept here rather than sent to a form service, because the useful half is
    the context nobody types: which page they were on, whether they were signed
    in, what they were using. "The numbers look wrong" is what people actually
    write, and that sentence is only actionable with the rest attached.
    """

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    message: Mapped[str] = mapped_column(Text)

    # Where they were when they hit the button, so a vague report still points
    # somewhere.
    page: Mapped[str | None] = mapped_column(String(200))
    user_agent: Mapped[str | None] = mapped_column(String(400))

    # Anyone can write, signed in or not — a visitor deciding whether to bother
    # signing up has the feedback most worth hearing. Kept if the account goes.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    email: Mapped[str | None] = mapped_column(String(320))

    status: Mapped[FeedbackStatus] = mapped_column(
        Enum(FeedbackStatus), default=FeedbackStatus.new, index=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True)
