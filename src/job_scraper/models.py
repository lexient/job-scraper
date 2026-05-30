from datetime import datetime
from typing import Any

from sqlalchemy import ARRAY, BigInteger, Column, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: str = Field(primary_key=True)
    source: str = Field(primary_key=True, index=True)
    title: str | None = None
    teaser: str | None = None
    company: str | None = None
    advertiser_id: str | None = None
    classification: str | None = None
    subclassification: str | None = None
    location: str | None = None
    work_type: str | None = None
    work_arrangement: str | None = None
    salary_label: str | None = None
    listing_date: str | None = None
    url: str | None = None
    role_id: str | None = None
    display_type: str | None = None
    is_featured: bool | None = None
    bullet_points: list[str] | None = Field(
        default=None, sa_column=Column(ARRAY(String))
    )
    tags: list[str] | None = Field(default=None, sa_column=Column(ARRAY(String)))
    raw_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB))
    raw_html: str | None = None
    html_hash: str | None = None
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
    misses: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    delisted_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    expired_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    content_hash: str | None = None
    content_changed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )


class JobDetail(SQLModel, table=True):
    __tablename__ = "job_details"

    id: str = Field(primary_key=True)
    source: str = Field(primary_key=True, index=True)
    title: str | None = None
    company: str | None = None
    location: str | None = None
    work_type: str | None = None
    salary: str | None = None
    rating: str | None = None
    classifications: list[str] | None = Field(
        default=None, sa_column=Column(ARRAY(String))
    )
    url: str | None = None
    markdown: str | None = None
    source_hash: str | None = None
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
    source: str = Field(index=True)
    job_id: str
    observed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    event: str
    content_hash: str | None = None
    html_hash: str | None = None
    raw_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB))
    markdown: str | None = None
