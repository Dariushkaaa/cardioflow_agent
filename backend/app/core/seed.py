"""Демо-данные для запуска "из коробки" (SEED_DEMO_DATA=true)."""
import datetime as dt
import logging
import uuid

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.core.timeutils import utcnow
from app.models.patient import Patient
from app.models.slot import AppointmentSlot

logger = logging.getLogger(__name__)

DEMO_PATIENT_ID = uuid.UUID("d3b07384-d113-4ec6-a563-9a3d46532401")


async def seed_demo_data() -> None:
    async with SessionLocal() as db:
        if await db.get(Patient, DEMO_PATIENT_ID) is None:
            db.add(
                Patient(
                    id=DEMO_PATIENT_ID,
                    full_name="Иванов Иван Иванович",
                    doctor_name="Иван Иваныч",
                    prescribed_medication="Периндоприл 5 мг",
                    frequency_per_day=2,
                    target_systolic=130,
                    target_diastolic=80,
                )
            )
            logger.info("Создан демо-пациент %s", DEMO_PATIENT_ID)

        slots_count = await db.scalar(select(func.count()).select_from(AppointmentSlot))
        if not slots_count:
            base = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            for day in range(1, 6):
                for hour, minute in ((10, 0), (14, 30)):
                    db.add(
                        AppointmentSlot(
                            doctor_id="therapist-1",
                            doctor_name="Иванов И.И.",
                            datetime=base + dt.timedelta(days=day, hours=hour, minutes=minute),
                        )
                    )
            logger.info("Созданы демо-слоты записи")
        await db.commit()
