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


def error(status: int, message: str) -> ErrorResponse:
    return ErrorResponse(status=status, payload={"ok": False, "error": message})
