import json
import urllib.request
import urllib.error
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings

router = APIRouter()


class ModeCommand(BaseModel):
    mode: Literal["AUTO", "MANUAL"]


@router.post("/control/mode")
def set_mode(command: ModeCommand):
    """Передаёт команду переключения режима в Python Gateway."""

    payload = json.dumps(
        {"mode": command.mode}
    ).encode("utf-8")

    request = urllib.request.Request(
        settings.GATEWAY_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.GATEWAY_TOKEN}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))

            return {
                "status": result.get("status"),
                "mode": result.get("mode"),
                "message": "Команда передана в Gateway",
            }

    except urllib.error.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail=f"Gateway отклонил запрос. HTTP {error.code}",
        )

    except (urllib.error.URLError, TimeoutError):
        raise HTTPException(
            status_code=502,
            detail="Gateway недоступен. Проверьте его работу.",
        )
