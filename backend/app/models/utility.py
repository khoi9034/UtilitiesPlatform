from __future__ import annotations

from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UtilitySystem(TimestampMixin, Base):
    __tablename__ = "utility_systems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    system_type: Mapped[str] = mapped_column(String(50), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str | None] = mapped_column(String(200))
    source_type: Mapped[str | None] = mapped_column(String(80))
    spatial_reference: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class UtilityLayer(TimestampMixin, Base):
    __tablename__ = "utility_layers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    utility_system_id: Mapped[int] = mapped_column(ForeignKey("utility_systems.id"), nullable=False)
    layer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_layer_name: Mapped[str | None] = mapped_column(String(200))
    geometry_type: Mapped[str | None] = mapped_column(String(80))
    network_group: Mapped[str | None] = mapped_column(String(120))
    asset_category: Mapped[str | None] = mapped_column(String(120))
    asset_subcategory: Mapped[str | None] = mapped_column(String(120))
    unique_id_field: Mapped[str | None] = mapped_column(String(120))
    source_path: Mapped[str | None] = mapped_column(Text)
    record_count: Mapped[int | None] = mapped_column(Integer)
    spatial_reference: Mapped[str | None] = mapped_column(String(120))
    last_inventory_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)


class UtilityAsset(TimestampMixin, Base):
    __tablename__ = "utility_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    utility_system_id: Mapped[int] = mapped_column(ForeignKey("utility_systems.id"), nullable=False)
    utility_layer_id: Mapped[int | None] = mapped_column(ForeignKey("utility_layers.id"))
    source_asset_id: Mapped[str | None] = mapped_column(String(200))
    asset_type: Mapped[str | None] = mapped_column(String(120))
    asset_subtype: Mapped[str | None] = mapped_column(String(120))
    asset_status: Mapped[str | None] = mapped_column(String(80))
    owner: Mapped[str | None] = mapped_column(String(200))
    material: Mapped[str | None] = mapped_column(String(120))
    diameter: Mapped[str | None] = mapped_column(String(80))
    installation_date: Mapped[date | None] = mapped_column(Date)
    inspection_date: Mapped[date | None] = mapped_column(Date)
    project_id: Mapped[str | None] = mapped_column(String(120))
    work_order_id: Mapped[str | None] = mapped_column(String(120))
    source_record: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    source_document: Mapped[str | None] = mapped_column(Text)
    geometry: Mapped[Any | None] = mapped_column(Geometry("GEOMETRY", srid=4326))


class DataSource(TimestampMixin, Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(Text)
    database_connection_name: Mapped[str | None] = mapped_column(String(200))
    source_owner: Mapped[str | None] = mapped_column(String(200))
    access_level: Mapped[str | None] = mapped_column(String(80))
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    refresh_method: Mapped[str | None] = mapped_column(String(120))
    last_refresh: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class QaRule(TimestampMixin, Base):
    __tablename__ = "qa_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    utility_system: Mapped[str | None] = mapped_column(String(50))
    network_group: Mapped[str | None] = mapped_column(String(120))
    asset_category: Mapped[str | None] = mapped_column(String(120))
    asset_subcategory: Mapped[str | None] = mapped_column(String(120))
    layer_type: Mapped[str | None] = mapped_column(String(120))
    severity: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class QaIssue(TimestampMixin, Base):
    __tablename__ = "qa_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    utility_system_id: Mapped[int | None] = mapped_column(ForeignKey("utility_systems.id"))
    utility_layer_id: Mapped[int | None] = mapped_column(ForeignKey("utility_layers.id"))
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("utility_assets.id"))
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("qa_rules.id"))
    issue_type: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    recommended_action: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str | None] = mapped_column(String(80))
    date_found: Mapped[date | None] = mapped_column(Date)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewer: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    geometry: Mapped[Any | None] = mapped_column(Geometry("GEOMETRY", srid=4326))


class CadSubmission(TimestampMixin, Base):
    __tablename__ = "cad_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String(120))
    submission_name: Mapped[str] = mapped_column(String(200), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_type: Mapped[str | None] = mapped_column(String(50))
    source_path: Mapped[str | None] = mapped_column(Text)
    contractor: Mapped[str | None] = mapped_column(String(200))
    utility_system: Mapped[str | None] = mapped_column(String(50))
    network_group: Mapped[str | None] = mapped_column(String(120))
    drawing_date: Mapped[date | None] = mapped_column(Date)
    submission_date: Mapped[date | None] = mapped_column(Date)
    coordinate_system: Mapped[str | None] = mapped_column(String(120))
    processing_status: Mapped[str | None] = mapped_column(String(80))
    review_status: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    project_name: Mapped[str] = mapped_column(String(200), nullable=False)
    utility_system: Mapped[str | None] = mapped_column(String(50))
    network_group: Mapped[str | None] = mapped_column(String(120))
    project_status: Mapped[str | None] = mapped_column(String(80))
    contractor: Mapped[str | None] = mapped_column(String(200))
    project_manager: Mapped[str | None] = mapped_column(String(200))
    planned_start_date: Mapped[date | None] = mapped_column(Date)
    planned_end_date: Mapped[date | None] = mapped_column(Date)
    completed_date: Mapped[date | None] = mapped_column(Date)
    redline_received: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gis_updated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    qa_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    project_geometry: Mapped[Any | None] = mapped_column(Geometry("GEOMETRY", srid=4326))
    notes: Mapped[str | None] = mapped_column(Text)


class EditLog(Base):
    __tablename__ = "edit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("utility_assets.id"))
    source_asset_id: Mapped[str | None] = mapped_column(String(200))
    layer_name: Mapped[str | None] = mapped_column(String(200))
    project_id: Mapped[str | None] = mapped_column(String(120))
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    previous_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    updated_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    edit_source: Mapped[str | None] = mapped_column(String(120))
    edited_by: Mapped[str | None] = mapped_column(String(200))
    edited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
