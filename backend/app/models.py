from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# =====================================================
# 1. УСТРОЙСТВА ESP32
# =====================================================

class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    device_uid: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="offline",
        nullable=False,
    )

    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    zones: Mapped[list["IrrigationZone"]] = relationship(
        back_populates="device",
    )

    readings: Mapped[list["SensorReading"]] = relationship(
        back_populates="device",
    )


# =====================================================
# 2. ЗОНЫ ПОЛИВА
# =====================================================

class IrrigationZone(Base):
    __tablename__ = "irrigation_zones"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id"),
        nullable=False,
    )

    zone_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    moisture_min: Mapped[float] = mapped_column(
        Float,
        default=35.0,
        nullable=False,
    )

    moisture_max: Mapped[float] = mapped_column(
        Float,
        default=60.0,
        nullable=False,
    )

    mode: Mapped[str] = mapped_column(
        String(20),
        default="AUTO",
        nullable=False,
    )

    irrigation_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    device: Mapped["Device"] = relationship(
        back_populates="zones",
    )

    readings: Mapped[list["SensorReading"]] = relationship(
        back_populates="zone",
    )

    events: Mapped[list["IrrigationEvent"]] = relationship(
        back_populates="zone",
    )


# =====================================================
# 3. ПОКАЗАНИЯ ДАТЧИКОВ
# =====================================================

class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id"),
        nullable=False,
    )

    zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("irrigation_zones.id"),
        nullable=True,
    )

    soil_moisture: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    temperature: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    air_humidity: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    light_level: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    rain_detected: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    device: Mapped["Device"] = relationship(
        back_populates="readings",
    )

    zone: Mapped["IrrigationZone | None"] = relationship(
        back_populates="readings",
    )


# =====================================================
# 4. СОБЫТИЯ ПОЛИВА
# =====================================================

class IrrigationEvent(Base):
    __tablename__ = "irrigation_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    zone_id: Mapped[int] = mapped_column(
        ForeignKey("irrigation_zones.id"),
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    zone: Mapped["IrrigationZone"] = relationship(
        back_populates="events",
    )
