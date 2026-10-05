"""Initial schema: patients, measurements, adherence logs, appointment slots

Revision ID: 0001
Revises:
Create Date: 2026-10-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("doctor_name", sa.String(length=255), nullable=False),
        sa.Column("target_systolic", sa.Integer(), server_default="130", nullable=False),
        sa.Column("target_diastolic", sa.Integer(), server_default="80", nullable=False),
        sa.Column("prescribed_medication", sa.String(length=255), nullable=True),
        sa.Column("frequency_per_day", sa.Integer(), server_default="2", nullable=False),
        sa.Column("morning_time", sa.Time(), server_default="09:00:00", nullable=False),
        sa.Column("evening_time", sa.Time(), server_default="21:00:00", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="active", nullable=False),
        sa.Column("quiet_hours_start", sa.Time(), server_default="22:00:00", nullable=False),
        sa.Column("quiet_hours_end", sa.Time(), server_default="08:00:00", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "blood_pressure_measurements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("systolic", sa.Integer(), nullable=True),
        sa.Column("diastolic", sa.Integer(), nullable=True),
        sa.Column("pulse", sa.Integer(), nullable=True),
        sa.Column("risk_status", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "medication_adherence_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("session_type", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("is_taken", sa.Boolean(), nullable=True),
        sa.Column("skip_reason", sa.String(length=50), nullable=True),
        sa.Column("raw_complaint", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("patient_id", "date", "session_type", name="uq_adherence_patient_date_session"),
    )
    op.create_table(
        "appointment_slots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("doctor_id", sa.String(length=100), nullable=False),
        sa.Column("doctor_name", sa.String(length=255), nullable=False),
        sa.Column("datetime", sa.DateTime(), nullable=False),
        sa.Column("is_booked", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("appointment_slots")
    op.drop_table("medication_adherence_logs")
    op.drop_table("blood_pressure_measurements")
    op.drop_table("patients")
