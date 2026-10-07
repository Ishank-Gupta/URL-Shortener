from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, relationship


def _utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class URL(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    short_code = Column(String(20), unique=True, nullable=False)
    original_url = Column(Text, nullable=False)
    custom_alias = Column(String(50), unique=True, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    click_count = Column(Integer, default=0, nullable=False)

    clicks = relationship("Click", back_populates="url", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_urls_short_code", "short_code"),
    )


class Click(Base):
    __tablename__ = "clicks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url_id = Column(Integer, ForeignKey("urls.id", ondelete="CASCADE"), nullable=False)
    clicked_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    referrer = Column(Text, nullable=True)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)

    url = relationship("URL", back_populates="clicks")

    __table_args__ = (
        Index("ix_clicks_url_id", "url_id"),
        Index("ix_clicks_clicked_at", "clicked_at"),
    )
