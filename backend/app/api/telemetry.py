from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Device, IrrigationZone, SensorReading
from app.schemas import TelemetryData


router = APIRouter()


@router.post("/telemetry", status_code=201)
async def receive_telemetry(
    payload: TelemetryData,
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    # 1. Ищем устройство по идентификатору
    result = await db.execute(
        select(Device).where(
            Device.device_uid == payload.device
        )
    )

    device = result.scalar_one_or_none()

    # 2. Регистрируем устройство, если оно ещё неизвестно
    if device is None:
        device = Device(
            device_uid=payload.device,
            name=payload.device,
            status="online",
            last_seen=now,
        )
        db.add(device)
        await db.flush()
    else:
        device.status = "online"
        device.last_seen = now

    # 3. Обрабатываем две зоны
    zones_data = [
        (1, payload.zone1),
        (2, payload.zone2),
    ]

    for zone_number, zone_data in zones_data:

        result = await db.execute(
            select(IrrigationZone).where(
                IrrigationZone.device_id == device.id,
                IrrigationZone.zone_number == zone_number,
            )
        )

        zone = result.scalar_one_or_none()

        # Создаём зону при первом получении данных
        if zone is None:
            zone = IrrigationZone(
                device_id=device.id,
                zone_number=zone_number,
                name=f"Зона {zone_number}",
                moisture_min=35.0,
                moisture_max=60.0,
                mode=payload.mode,
                irrigation_active=zone_data.irrigation,
            )
            db.add(zone)
            await db.flush()

        else:
            zone.mode = payload.mode
            zone.irrigation_active = zone_data.irrigation

        # 4. Сохраняем показания датчиков
        reading = SensorReading(
            device_id=device.id,
            zone_id=zone.id,
            soil_moisture=zone_data.soil,
            temperature=payload.air.temperature,
            air_humidity=payload.air.humidity,
            light_level=float(payload.light_adc),
            rain_detected=payload.raining,
        )

        db.add(reading)

    # 5. Сохраняем изменения в PostgreSQL
    await db.commit()

    return {
        "status": "saved",
        "device": device.device_uid,
        "readings_saved": 2,
        "zones": [1, 2],
    }
