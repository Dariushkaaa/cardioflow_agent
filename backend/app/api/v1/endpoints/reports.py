import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websockets.manager import manager
from app.core.database import get_db
from app.core.security import ensure_patient_access, get_current_patient_id
from app.core.timeutils import now_local
from app.models.measurement import BloodPressureMeasurement
from app.models.patient import Patient
from app.schemas.report import ReportCreate, ReportResponse
from app.services import risk_engine
from app.services.adherence_service import register_medication_report

router = APIRouter()


@router.post("/", response_model=ReportResponse)
async def create_report(
    payload: ReportCreate,
    db: AsyncSession = Depends(get_db),
    token_patient_id: uuid.UUID = Depends(get_current_patient_id),
) -> ReportResponse:
    """Структурированный отчет от AI-агента (Tool Calling) от лица пациента."""
    ensure_patient_access(token_patient_id, payload.patient_id)
    patient = await db.get(Patient, payload.patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    now = now_local()
    pid = str(patient.id)

    # 1. Оценка риска (детерминированный движок) и запись замера
    risk_level = risk_engine.assess_risk(
        payload.systolic,
        payload.diastolic,
        payload.pulse,
        patient.target_systolic,
        patient.target_diastolic,
    )
    has_pressure = payload.systolic is not None and payload.diastolic is not None
    # id и время замера попадают и в БД, и в событие new_measurement_status: по ним фронтенд сразу
    # добавляет точку на график (и не дублирует ее, когда потом перечитывает историю с сервера)
    measurement_id = uuid.uuid4()
    if risk_level is not None:
        db.add(
            BloodPressureMeasurement(
                id=measurement_id,
                patient_id=patient.id,
                timestamp=now,
                systolic=payload.systolic,
                diastolic=payload.diastolic,
                pulse=payload.pulse,
                risk_status=risk_level,
            )
        )

    # 2. Прием / пропуск таблетки
    if payload.medication_taken is not None:
        await register_medication_report(
            db, patient, now, payload.medication_taken, payload.skip_reason, payload.raw_complaint
        )

    # 3. Пациент вышел на связь: снимаем статус потери контакта
    reactivated = patient.status == "lost_to_follow_up"
    if reactivated:
        patient.status = "active"

    await db.commit()

    # 4. Решение и события для интерфейса
    action = risk_engine.decide_action(risk_level, payload.skip_reason)

    if reactivated:
        await manager.send_event(pid, "patient_status_update", {"status": "active"})
    if risk_level is not None:
        await manager.send_event(
            pid,
            "new_measurement_status",
            {
                "id": str(measurement_id),
                "timestamp": now.isoformat(),
                "systolic": payload.systolic,
                "diastolic": payload.diastolic,
                "pulse": payload.pulse,
                "risk_status": risk_level,
            },
        )
    if action == risk_engine.ACTION_BOOK_APPOINTMENT:
        reason = risk_engine.build_escalation_reason(risk_level, payload.skip_reason, has_pressure)
        await manager.send_event(pid, "show_appointment_slots", {"reason": reason})

    message = "Данные успешно сохранены."
    if action == risk_engine.ACTION_BOOK_APPOINTMENT:
        message = "Данные успешно сохранены, запущен протокол эскалации."

    return ReportResponse(
        status="success",
        risk_level=risk_level or "unknown",
        action_required=action,
        message=message,
    )
