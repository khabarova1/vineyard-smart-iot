from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Device, IrrigationZone, SensorReading


router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    # Получаем зарегистрированные устройства
    devices_result = await db.execute(
        select(Device)
    )
    devices = devices_result.scalars().all()

    # Получаем зоны полива
    zones_result = await db.execute(
        select(IrrigationZone).order_by(IrrigationZone.zone_number)
    )
    zones = zones_result.scalars().all()

    # Получаем последние показания датчиков
    readings_result = await db.execute(
        select(SensorReading)
        .order_by(desc(SensorReading.recorded_at))
        .limit(20)
    )
    readings = readings_result.scalars().all()

    return {
        "devices": [
            {
                "id": device.id,
                "name": device.name,
                "device_uid": device.device_uid,
                "status": device.status,
                "last_seen": device.last_seen,
            }
            for device in devices
        ],
        "zones": [
            {
                "id": zone.id,
                "number": zone.zone_number,
                "name": zone.name,
                "mode": zone.mode,
                "soil_moisture_min": zone.moisture_min,
                "soil_moisture_max": zone.moisture_max,
                "irrigation_active": zone.irrigation_active,
            }
            for zone in zones
        ],
        "readings": [
            {
                "id": reading.id,
                "zone_id": reading.zone_id,
                "soil_moisture": reading.soil_moisture,
                "temperature": reading.temperature,
                "air_humidity": reading.air_humidity,
                "light_level": reading.light_level,
                "rain_detected": reading.rain_detected,
                "recorded_at": reading.recorded_at,
            }
            for reading in readings
        ],
    }

@router.get("/history")
async def get_history(
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SensorReading)
        .order_by(SensorReading.recorded_at.asc())
        .limit(limit)
    )

    readings = result.scalars().all()

    return {
        "count": len(readings),
        "readings": [
            {
                "id": reading.id,
                "zone_id": reading.zone_id,
                "soil_moisture": reading.soil_moisture,
                "temperature": reading.temperature,
                "air_humidity": reading.air_humidity,
                "recorded_at": reading.recorded_at,
            }
            for reading in readings
        ],
    }
