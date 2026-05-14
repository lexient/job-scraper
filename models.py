from datetime import datetime
from typing import Any

from sqlalchemy import ARRAY, BigInteger, Column, DateTime, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: str = Field(primary_key=True, sa_type=Text)
    title: str | None = Field(default=None, sa_type=Text)
    teaser: str | None = Field(default=None, sa_type=Text)
    company: str | None = Field(default=None, sa_type=Text)
    advertiser_id: str | None = Field(default=None, sa_type=Text)
    classification: str | None = Field(default=None, sa_type=Text)
    subclassification: str | None = Field(default=None, sa_type=Text)
    location: str | None = Field(default=None, sa_type=Text)
    work_type: str | None = Field(default=None, sa_type=Text)
    work_arrangement: str | None = Field(default=None, sa_type=Text)
    salary_label: str | None = Field(default=None, sa_type=Text)
    listing_date: str | None = Field(default=None, sa_type=Text)
    url: str | None = Field(default=None, sa_type=Text)
    role_id: str | None = Field(default=None, sa_type=Text)
    display_type: str | None = Field(default=None, sa_type=Text)
    is_featured: bool | None = None
    bullet_points: list[str] | None = Field(default=None, sa_column=Column(ARRAY(Text)))
    tags: list[str] | None = Field(default=None, sa_column=Column(ARRAY(Text)))
    raw_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB))
    raw_html: str | None = Field(default=None, sa_type=Text)
    html_hash: str | None = Field(default=None, sa_type=Text)
    html_fetched_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    scraped_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    last_seen_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    delisted_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    expired_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    content_hash: str | None = Field(default=None, sa_type=Text)
    content_changed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )


class JobDetail(SQLModel, table=True):
    __tablename__ = "job_details"

    id: str = Field(primary_key=True, sa_type=Text)
    title: str | None = Field(default=None, sa_type=Text)
    company: str | None = Field(default=None, sa_type=Text)
    location: str | None = Field(default=None, sa_type=Text)
    work_type: str | None = Field(default=None, sa_type=Text)
    salary: str | None = Field(default=None, sa_type=Text)
    rating: str | None = Field(default=None, sa_type=Text)
    classifications: list[str] | None = Field(
        default=None, sa_column=Column(ARRAY(Text))
    )
    url: str | None = Field(default=None, sa_type=Text)
    markdown: str | None = Field(default=None, sa_type=Text)
    source_hash: str | None = Field(default=None, sa_type=Text)
    cleaned_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )


class JobHistory(SQLModel, table=True):
    __tablename__ = "job_history"
    __table_args__ = (
        Index("job_history_job_id_idx", "job_id", "observed_at"),
        Index("job_history_event_idx", "event", "observed_at"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    job_id: str = Field(sa_type=Text)
    observed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    event: str = Field(sa_type=Text)
    content_hash: str | None = Field(default=None, sa_type=Text)
    html_hash: str | None = Field(default=None, sa_type=Text)
    raw_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB))
    markdown: str | None = Field(default=None, sa_type=Text)
