"""Initial utility platform schema."""

from alembic import op
import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260719_0001"
down_revision = None
branch_labels = None
depends_on = None


def timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "utility_systems",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("system_type", sa.String(length=50), nullable=False),
        sa.Column("owner", sa.String(length=200)),
        sa.Column("description", sa.Text()),
        sa.Column("source_name", sa.String(length=200)),
        sa.Column("source_type", sa.String(length=80)),
        sa.Column("spatial_reference", sa.String(length=120)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *timestamps(),
    )

    op.create_table(
        "data_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("file_path", sa.Text()),
        sa.Column("database_connection_name", sa.String(length=200)),
        sa.Column("source_owner", sa.String(length=200)),
        sa.Column("access_level", sa.String(length=80)),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("refresh_method", sa.String(length=120)),
        sa.Column("last_refresh", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        *timestamps(),
    )

    op.create_table(
        "qa_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_name", sa.String(length=200), nullable=False),
        sa.Column("rule_code", sa.String(length=120), nullable=False, unique=True),
        sa.Column("utility_system", sa.String(length=50)),
        sa.Column("network_group", sa.String(length=120)),
        sa.Column("asset_category", sa.String(length=120)),
        sa.Column("asset_subcategory", sa.String(length=120)),
        sa.Column("layer_type", sa.String(length=120)),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *timestamps(),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.String(length=120), nullable=False, unique=True),
        sa.Column("project_name", sa.String(length=200), nullable=False),
        sa.Column("utility_system", sa.String(length=50)),
        sa.Column("network_group", sa.String(length=120)),
        sa.Column("project_status", sa.String(length=80)),
        sa.Column("contractor", sa.String(length=200)),
        sa.Column("project_manager", sa.String(length=200)),
        sa.Column("planned_start_date", sa.Date()),
        sa.Column("planned_end_date", sa.Date()),
        sa.Column("completed_date", sa.Date()),
        sa.Column("redline_received", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("gis_updated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("qa_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("project_geometry", geoalchemy2.Geometry("GEOMETRY", srid=4326)),
        sa.Column("notes", sa.Text()),
        *timestamps(),
    )

    op.create_table(
        "utility_layers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("utility_system_id", sa.Integer(), sa.ForeignKey("utility_systems.id"), nullable=False),
        sa.Column("layer_name", sa.String(length=200), nullable=False),
        sa.Column("source_layer_name", sa.String(length=200)),
        sa.Column("geometry_type", sa.String(length=80)),
        sa.Column("network_group", sa.String(length=120)),
        sa.Column("asset_category", sa.String(length=120)),
        sa.Column("asset_subcategory", sa.String(length=120)),
        sa.Column("unique_id_field", sa.String(length=120)),
        sa.Column("source_path", sa.Text()),
        sa.Column("record_count", sa.Integer()),
        sa.Column("spatial_reference", sa.String(length=120)),
        sa.Column("last_inventory_date", sa.Date()),
        sa.Column("notes", sa.Text()),
        *timestamps(),
    )

    op.create_table(
        "utility_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("utility_system_id", sa.Integer(), sa.ForeignKey("utility_systems.id"), nullable=False),
        sa.Column("utility_layer_id", sa.Integer(), sa.ForeignKey("utility_layers.id")),
        sa.Column("source_asset_id", sa.String(length=200)),
        sa.Column("asset_type", sa.String(length=120)),
        sa.Column("asset_subtype", sa.String(length=120)),
        sa.Column("asset_status", sa.String(length=80)),
        sa.Column("owner", sa.String(length=200)),
        sa.Column("material", sa.String(length=120)),
        sa.Column("diameter", sa.String(length=80)),
        sa.Column("installation_date", sa.Date()),
        sa.Column("inspection_date", sa.Date()),
        sa.Column("project_id", sa.String(length=120)),
        sa.Column("work_order_id", sa.String(length=120)),
        sa.Column("source_record", postgresql.JSONB()),
        sa.Column("source_document", sa.Text()),
        sa.Column("geometry", geoalchemy2.Geometry("GEOMETRY", srid=4326)),
        *timestamps(),
    )

    op.create_table(
        "qa_issues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("utility_system_id", sa.Integer(), sa.ForeignKey("utility_systems.id")),
        sa.Column("utility_layer_id", sa.Integer(), sa.ForeignKey("utility_layers.id")),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("utility_assets.id")),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("qa_rules.id")),
        sa.Column("issue_type", sa.String(length=120), nullable=False),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("recommended_action", sa.Text()),
        sa.Column("review_status", sa.String(length=80)),
        sa.Column("date_found", sa.Date()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("reviewer", sa.String(length=200)),
        sa.Column("notes", sa.Text()),
        sa.Column("geometry", geoalchemy2.Geometry("GEOMETRY", srid=4326)),
        *timestamps(),
    )

    op.create_table(
        "cad_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.String(length=120)),
        sa.Column("submission_name", sa.String(length=200), nullable=False),
        sa.Column("file_name", sa.String(length=255)),
        sa.Column("file_type", sa.String(length=50)),
        sa.Column("source_path", sa.Text()),
        sa.Column("contractor", sa.String(length=200)),
        sa.Column("utility_system", sa.String(length=50)),
        sa.Column("network_group", sa.String(length=120)),
        sa.Column("drawing_date", sa.Date()),
        sa.Column("submission_date", sa.Date()),
        sa.Column("coordinate_system", sa.String(length=120)),
        sa.Column("processing_status", sa.String(length=80)),
        sa.Column("review_status", sa.String(length=80)),
        sa.Column("notes", sa.Text()),
        *timestamps(),
    )

    op.create_table(
        "edit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("utility_assets.id")),
        sa.Column("source_asset_id", sa.String(length=200)),
        sa.Column("layer_name", sa.String(length=200)),
        sa.Column("project_id", sa.String(length=120)),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("previous_values", postgresql.JSONB()),
        sa.Column("updated_values", postgresql.JSONB()),
        sa.Column("edit_source", sa.String(length=120)),
        sa.Column("edited_by", sa.String(length=200)),
        sa.Column("edited_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("notes", sa.Text()),
    )


def downgrade() -> None:
    op.drop_table("edit_log")
    op.drop_table("cad_submissions")
    op.drop_table("qa_issues")
    op.drop_table("utility_assets")
    op.drop_table("utility_layers")
    op.drop_table("projects")
    op.drop_table("qa_rules")
    op.drop_table("data_sources")
    op.drop_table("utility_systems")
