from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass

from doubaoime_asr import ASRConfig, ASRError, ResponseType, transcribe_stream


@dataclass(slots=True)
class TranscriptionResult:
    text: str
    segments: list[str]
    audio_format: str
    sample_rate: int
    channels: int
    device_id: str


class ASRService:
    def __init__(self, credential_path: str):
        self.credential_path = credential_path

    def transcribe_bytes(
        self,
        audio_data: bytes,
        *,
        sample_rate: int,
        channels: int,
        audio_format: str,
        device_id: str,
        enable_punctuation: bool = True,
        realtime: bool = True,
    ) -> TranscriptionResult:
        config = ASRConfig(
            credential_path=self.credential_path,
            sample_rate=sample_rate,
            channels=channels,
            enable_punctuation=enable_punctuation,
        )
        text, segments = asyncio.run(
            self._transcribe_with_log(
                audio_data,
                config,
                device_id=device_id,
                realtime=realtime,
            )
        )
        return TranscriptionResult(
            text=text,
            segments=segments,
            audio_format=audio_format,
            sample_rate=sample_rate,
            channels=channels,
            device_id=device_id,
        )

    async def _transcribe_with_log(
        self,
        audio_data: bytes,
        config: ASRConfig,
        *,
        device_id: str,
        realtime: bool,
    ) -> tuple[str, list[str]]:
        sample_count = len(audio_data) // 2
        if sample_count > 0:
            samples = struct.unpack(f"<{sample_count}h", audio_data[: sample_count * 2])
            peak = max(abs(s) for s in samples)
            rms = int((sum(s * s for s in samples) / sample_count) ** 0.5)
        else:
            peak, rms = 0, 0
        duration_s = len(audio_data) / max(config.sample_rate * config.channels * 2, 1)
        print(
            f"[audio] {device_id}: bytes={len(audio_data)}"
            f"  dur={duration_s:.2f}s  peak={peak}  rms={rms}"
        )

        final_parts: list[str] = []
        async for resp in transcribe_stream(audio_data, config=config, realtime=realtime):
            text_val = getattr(resp, "text", "") or ""
            err_val = getattr(resp, "error_msg", "") or ""
            print(f"[asr]  {resp.type.name:<20}  text={text_val!r}  err={err_val!r}")
            if resp.type == ResponseType.FINAL_RESULT:
                if text_val:
                    final_parts.append(text_val)
            elif resp.type == ResponseType.ERROR:
                raise ASRError(err_val, resp)

        result = "".join(final_parts)
        print(f"[done] {device_id}: final={result!r}  parts={len(final_parts)}")
        return result, final_parts
