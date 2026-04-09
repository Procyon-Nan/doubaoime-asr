from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ErrorResponse:
    status: int
    payload: dict[str, Any]


@dataclass(slots=True)
class LegacyRequest:
    audio_data: bytes
    sample_rate: int
    channels: int
    audio_format: str
    device_id: str


@dataclass(slots=True)
class StandardRequest:
    audio_data: bytes
    sample_rate: int
    channels: int
    audio_format: str
    device_id: str
    enable_punctuation: bool = True
    realtime: bool = True


def ok_text(text: str) -> dict[str, Any]:
    return {"ok": True, "text": text}


def ok_transcription(
    text: str,
    *,
    segments: list[str],
    audio_format: str,
    sample_rate: int,
    channels: int,
    device_id: str,
) -> dict[str, Any]:
    return {
        "ok": True,
        "text": text,
        "segments": segments,
        "meta": {
            "audio_format": audio_format,
            "sample_rate": sample_rate,
            "channels": channels,
            "device_id": device_id,
        },
    }


def ok_aliyun(result: str, *, task_id: str = "") -> dict[str, Any]:
    return {
        "task_id": task_id,
        "result": result,
        "status": 20000000,
        "message": "SUCCESS",
    }


def error_aliyun(message: str, *, task_id: str = "", status_code: int = 40000000) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "result": "",
        "status": status_code,
        "message": message,
    }


def error(status: int, message: str) -> ErrorResponse:
    return ErrorResponse(status=status, payload={"ok": False, "error": message})
