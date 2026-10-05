import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import ensure_patient_access, get_current_patient_id
from app.models.measurement import BloodPressureMeasurement
from app.models.patient import Patient
from app.schemas.patient import LatestMeasurement, MeasurementOut, ScheduleResponse, ScheduleUpdate, TreatmentPlan
from app.services.schedule_validator import ScheduleValidationError, validate_schedule

router = APIRouter()


@router.get("/treatment-plan", response_model=TreatmentPlan)
async def get_treatment_plan(
    db: AsyncSession = Depends(get_db),
    patient_id: uuid.UUID = Depends(get_current_patient_id),
) -> TreatmentPlan:
    """Назначения врача и целевые показатели пациента (контекст для агента)."""
    patient = await db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    return TreatmentPlan(
        patient_id=patient.id,
        full_name=patient.full_name,
        doctor_name=patient.doctor_name,
        prescribed_medication=patient.prescribed_medication,
        frequency_per_day=patient.frequency_per_day,
        target_systolic=patient.target_systolic,
        target_diastolic=patient.target_diastolic,
        morning_time=patient.morning_time,
        evening_time=patient.evening_time,
    )


@router.get("/measurements", response_model=list[MeasurementOut])
async def list_measurements(
    limit: int = Query(default=30, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    patient_id: uuid.UUID = Depends(get_current_patient_id),
) -> list[BloodPressureMeasurement]:
    """История замеров для графика: последние `limit` записей по возрастанию времени."""
    result = await db.scalars(
        select(BloodPressureMeasurement)
        .where(BloodPressureMeasurement.patient_id == patient_id)
        .order_by(BloodPressureMeasurement.timestamp.desc())
        .limit(limit)
    )
    return list(reversed(result.all()))


@router.get("/measurements/latest", response_model=Optional[LatestMeasurement])
async def get_latest_measurement(
    db: AsyncSession = Depends(get_db),
    patient_id: uuid.UUID = Depends(get_current_patient_id),
) -> Optional[BloodPressureMeasurement]:
    """Последний сохраненный замер пациента (null, если замеров еще не было)."""
    return await db.scalar(
        select(BloodPressureMeasurement)
        .where(BloodPressureMeasurement.patient_id == patient_id)
        .order_by(BloodPressureMeasurement.timestamp.desc())
        .limit(1)
    )


@router.post("/schedule", response_model=ScheduleResponse)
async def save_schedule(
    payload: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    token_patient_id: uuid.UUID = Depends(get_current_patient_id),
) -> ScheduleResponse:
    """Сохранение и валидация интервалов утреннего и вечернего приема лекарств."""
    ensure_patient_access(token_patient_id, payload.patient_id)
    patient = await db.get(Patient, payload.patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    try:
        validate_schedule(payload.morning_time, payload.evening_time)
    except ScheduleValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    patient.morning_time = payload.morning_time
    patient.evening_time = payload.evening_time
    await db.commit()
    return ScheduleResponse(status="validated_and_saved")
