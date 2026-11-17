from pydantic import BaseModel, ConfigDict, Field


class ZoneTelemetry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    soil: float = Field(ge=0, le=100)
    soil_adc: int | None = Field(default=None, ge=0, le=4095)
    irrigation: bool
    sensor_valid: bool


class AirTelemetry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    temperature: float
    humidity: float = Field(ge=0, le=100)
    valid: bool


class TelemetryData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    device: str = Field(min_length=1, max_length=100)
    mode: str
    zone1: ZoneTelemetry
    zone2: ZoneTelemetry
    air: AirTelemetry
    light_adc: int = Field(ge=0, le=4095)
    rain_adc: int = Field(ge=0, le=4095)
    raining: bool
