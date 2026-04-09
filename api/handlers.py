from __future__ import annotations

import base64
import cgi
import io
import json
import wave
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.parse import parse_qs, urlsplit

from doubaoime_asr import ASRError

from .schemas import (
    ErrorResponse,
    LegacyRequest,
    StandardRequest,
    error,
    error_aliyun,
    ok_aliyun,
    ok_text,
    ok_transcription,
)


class ASRRequestHandler(BaseHTTPRequestHandler):
    server_version = "DoubaoASRAPI/0.1"

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == self.server.options.health_path:
            self._send_json(
                HTTPStatus.OK,
                {"ok": True, "service": self.server.options.service_name},
            )
            return
        self._send_error(error(HTTPStatus.NOT_FOUND, "not found"))

    def do_POST(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == self.server.options.bridge_path:
            self._handle_legacy_transcribe()
            return
        if parsed.path == self.server.options.standard_path:
            self._handle_standard_transcribe()
            return
        if parsed.path == self.server.options.aliyun_path:
            self._handle_aliyun_transcribe(parsed.query)
            return
        self._send_error(error(HTTPStatus.NOT_FOUND, "not found"))

    def _handle_legacy_transcribe(self) -> None:
        request = self._parse_legacy_request()
        if isinstance(request, ErrorResponse):
            self._send_error(request)
            return

        try:
            result = self.server.service.transcribe_bytes(
                request.audio_data,
                sample_rate=request.sample_rate,
                channels=request.channels,
                audio_format=request.audio_format,
                device_id=request.device_id,
                enable_punctuation=True,
                realtime=True,
            )
        except ASRError as exc:
            self.log_error("ASR failed for device %s: %s", request.device_id, exc)
            self._send_error(error(HTTPStatus.BAD_GATEWAY, str(exc)))
            return
        except Exception as exc:  # noqa: BLE001
            self.log_error("Unexpected error for device %s: %s", request.device_id, exc)
            self._send_error(error(HTTPStatus.INTERNAL_SERVER_ERROR, "internal server error"))
            return

        self.log_message("ASR success for %s: %r", request.device_id, result.text)
        self._send_json(HTTPStatus.OK, ok_text(result.text))

    def _handle_standard_transcribe(self) -> None:
        request = self._parse_standard_request()
        if isinstance(request, ErrorResponse):
            self._send_error(request)
            return

        try:
            result = self.server.service.transcribe_bytes(
                request.audio_data,
                sample_rate=request.sample_rate,
                channels=request.channels,
                audio_format=request.audio_format,
                device_id=request.device_id,
                enable_punctuation=request.enable_punctuation,
                realtime=request.realtime,
            )
        except ASRError as exc:
            self.log_error("ASR failed for device %s: %s", request.device_id, exc)
            self._send_error(error(HTTPStatus.BAD_GATEWAY, str(exc)))
            return
        except Exception as exc:  # noqa: BLE001
            self.log_error("Unexpected error for device %s: %s", request.device_id, exc)
            self._send_error(error(HTTPStatus.INTERNAL_SERVER_ERROR, "internal server error"))
            return

        self.log_message("STT success for %s: %r", request.device_id, result.text)
        self._send_json(
            HTTPStatus.OK,
            ok_transcription(
                result.text,
                segments=result.segments,
                audio_format=result.audio_format,
                sample_rate=result.sample_rate,
                channels=result.channels,
                device_id=result.device_id,
            ),
        )

    def _handle_aliyun_transcribe(self, query: str) -> None:
        request = self._parse_aliyun_request(query)
        if isinstance(request, ErrorResponse):
            self._send_json(request.status, request.payload)
            return

        try:
            result = self.server.service.transcribe_bytes(
                request.audio_data,
                sample_rate=request.sample_rate,
                channels=request.channels,
                audio_format=request.audio_format,
                device_id=request.device_id,
                enable_punctuation=request.enable_punctuation,
                realtime=True,
            )
        except ASRError as exc:
            self.log_error("Aliyun-compatible ASR failed for device %s: %s", request.device_id, exc)
            self._send_json(
                HTTPStatus.BAD_GATEWAY,
                error_aliyun(str(exc), task_id="", status_code=50000000),
            )
            return
        except Exception as exc:  # noqa: BLE001
            self.log_error("Unexpected aliyun-compatible error for device %s: %s", request.device_id, exc)
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                error_aliyun("internal server error", task_id="", status_code=50000001),
            )
            return

        self.log_message("Aliyun-compatible STT success for %s: %r", request.device_id, result.text)
        self._send_json(HTTPStatus.OK, ok_aliyun(result.text, task_id=""))

    def _parse_legacy_request(self) -> LegacyRequest | ErrorResponse:
        body = self._read_request_body()
        if isinstance(body, ErrorResponse):
            return body

        sample_rate = self.headers.get("X-Sample-Rate", "16000")
        channels = self.headers.get("X-Channels", "1")
        audio_format = self.headers.get("X-Audio-Format", "pcm_s16le")
        device_id = self.headers.get("X-Device-Id", "unknown")

        try:
            sample_rate_int = int(sample_rate)
            channels_int = int(channels)
        except ValueError:
            return error(HTTPStatus.BAD_REQUEST, "invalid audio metadata")

        if audio_format != "pcm_s16le":
            return error(HTTPStatus.BAD_REQUEST, "unsupported audio format")

        return LegacyRequest(
            audio_data=body,
            sample_rate=sample_rate_int,
            channels=channels_int,
            audio_format=audio_format,
            device_id=device_id,
        )

    def _parse_standard_request(self) -> StandardRequest | ErrorResponse:
        content_type = self.headers.get("Content-Type", "")
        if content_type.startswith("application/json"):
            return self._parse_standard_json_request()
        if content_type.startswith("multipart/form-data"):
            return self._parse_standard_multipart_request()
        return error(HTTPStatus.BAD_REQUEST, "unsupported content type")

    def _parse_standard_json_request(self) -> StandardRequest | ErrorResponse:
        body = self._read_request_body()
        if isinstance(body, ErrorResponse):
            return body

        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return error(HTTPStatus.BAD_REQUEST, "invalid json body")

        audio = payload.get("audio")
        if not isinstance(audio, dict):
            return error(HTTPStatus.BAD_REQUEST, "missing audio object")

        content_base64 = audio.get("content_base64")
        if not isinstance(content_base64, str) or not content_base64:
            return error(HTTPStatus.BAD_REQUEST, "missing audio.content_base64")

        try:
            audio_data = base64.b64decode(content_base64, validate=True)
        except (ValueError, TypeError):
            return error(HTTPStatus.BAD_REQUEST, "invalid audio.content_base64")

        audio_format = audio.get("format", "pcm_s16le")
        sample_rate = audio.get("sample_rate", 16000)
        channels = audio.get("channels", 1)
        options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
        device_id = payload.get("device_id", "unknown")
        enable_punctuation = options.get("enable_punctuation", True)
        realtime = options.get("realtime", True)

        try:
            sample_rate_int = int(sample_rate)
            channels_int = int(channels)
        except (ValueError, TypeError):
            return error(HTTPStatus.BAD_REQUEST, "invalid audio metadata")

        if audio_format != "pcm_s16le":
            return error(HTTPStatus.BAD_REQUEST, "unsupported audio format")
        if not isinstance(device_id, str) or not device_id:
            return error(HTTPStatus.BAD_REQUEST, "invalid device_id")
        if not isinstance(enable_punctuation, bool) or not isinstance(realtime, bool):
            return error(HTTPStatus.BAD_REQUEST, "invalid options")

        return StandardRequest(
            audio_data=audio_data,
            sample_rate=sample_rate_int,
            channels=channels_int,
            audio_format=audio_format,
            device_id=device_id,
            enable_punctuation=enable_punctuation,
            realtime=realtime,
        )

    def _parse_standard_multipart_request(self) -> StandardRequest | ErrorResponse:
        content_type = self.headers.get("Content-Type", "")
        content_length = self.headers.get("Content-Length", "0")
        try:
            body_len = int(content_length)
        except ValueError:
            return error(HTTPStatus.BAD_REQUEST, "invalid content length")

        if body_len <= 0:
            return error(HTTPStatus.BAD_REQUEST, "empty audio body")
        if body_len > self.server.options.max_body_bytes:
            return error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "audio too large")

        environ = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": content_type,
            "CONTENT_LENGTH": str(body_len),
        }
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ=environ,
            keep_blank_values=True,
        )

        file_item = form["file"] if "file" in form else None
        if file_item is None or file_item.file is None:
            return error(HTTPStatus.BAD_REQUEST, "missing multipart file")

        audio_data = file_item.file.read()
        if not audio_data:
            return error(HTTPStatus.BAD_REQUEST, "empty audio body")
        if len(audio_data) > self.server.options.max_body_bytes:
            return error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "audio too large")

        audio_format = self._multipart_value(form, "format", "pcm_s16le")
        sample_rate = self._multipart_value(form, "sample_rate", "16000")
        channels = self._multipart_value(form, "channels", "1")
        device_id = self._multipart_value(form, "device_id", "unknown")
        enable_punctuation = self._parse_bool(
            self._multipart_value(form, "enable_punctuation", "true")
        )
        realtime = self._parse_bool(self._multipart_value(form, "realtime", "true"))

        try:
            sample_rate_int = int(sample_rate)
            channels_int = int(channels)
        except ValueError:
            return error(HTTPStatus.BAD_REQUEST, "invalid audio metadata")

        if audio_format != "pcm_s16le":
            return error(HTTPStatus.BAD_REQUEST, "unsupported audio format")
        if enable_punctuation is None or realtime is None:
            return error(HTTPStatus.BAD_REQUEST, "invalid options")

        return StandardRequest(
            audio_data=audio_data,
            sample_rate=sample_rate_int,
            channels=channels_int,
            audio_format=audio_format,
            device_id=device_id,
            enable_punctuation=enable_punctuation,
            realtime=realtime,
        )

    def _parse_aliyun_request(self, query: str) -> StandardRequest | ErrorResponse:
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("application/octet-stream"):
            return ErrorResponse(
                status=HTTPStatus.BAD_REQUEST,
                payload=error_aliyun("unsupported content type", status_code=40000001),
            )

        params = parse_qs(query, keep_blank_values=True)
        audio_format = self._query_value(params, "format", "wav")
        sample_rate = self._query_value(params, "sample_rate", "16000")
        enable_punctuation_raw = self._query_value(
            params, "enable_punctuation_prediction", "false"
        )
        appkey = self._query_value(params, "appkey", "")
        token = self.headers.get("X-NLS-Token", "")
        device_id = f"tlm-aliyun:{appkey or token or 'unknown'}"

        if audio_format.lower() != "wav":
            return ErrorResponse(
                status=HTTPStatus.BAD_REQUEST,
                payload=error_aliyun("unsupported audio format", status_code=40000002),
            )

        try:
            sample_rate_int = int(sample_rate)
        except ValueError:
            return ErrorResponse(
                status=HTTPStatus.BAD_REQUEST,
                payload=error_aliyun("invalid sample_rate", status_code=40000003),
            )

        enable_punctuation = self._parse_bool(enable_punctuation_raw)
        if enable_punctuation is None:
            return ErrorResponse(
                status=HTTPStatus.BAD_REQUEST,
                payload=error_aliyun("invalid enable_punctuation_prediction", status_code=40000004),
            )

        body = self._read_request_body()
        if isinstance(body, ErrorResponse):
            return ErrorResponse(
                status=body.status,
                payload=error_aliyun(body.payload["error"], status_code=40000005),
            )

        try:
            pcm_data, wav_sample_rate, channels = self._decode_wav(body)
        except (wave.Error, ValueError):
            return ErrorResponse(
                status=HTTPStatus.BAD_REQUEST,
                payload=error_aliyun("invalid wav body", status_code=40000006),
            )

        return StandardRequest(
            audio_data=pcm_data,
            sample_rate=wav_sample_rate or sample_rate_int,
            channels=channels,
            audio_format="pcm_s16le",
            device_id=device_id,
            enable_punctuation=enable_punctuation,
            realtime=True,
        )

    @staticmethod
    def _decode_wav(body: bytes) -> tuple[bytes, int, int]:
        with wave.open(io.BytesIO(body), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frames = wav_file.readframes(wav_file.getnframes())
        if sample_width != 2:
            raise ValueError("unsupported wav sample width")
        return frames, sample_rate, channels

    @staticmethod
    def _query_value(params: dict[str, list[str]], name: str, default: str) -> str:
        values = params.get(name)
        if not values:
            return default
        return values[0]

    def _read_request_body(self) -> bytes | ErrorResponse:
        content_length = self.headers.get("Content-Length", "0")
        try:
            body_len = int(content_length)
        except ValueError:
            return error(HTTPStatus.BAD_REQUEST, "invalid content length")

        if body_len <= 0:
            return error(HTTPStatus.BAD_REQUEST, "empty audio body")
        if body_len > self.server.options.max_body_bytes:
            return error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "audio too large")

        body = self.rfile.read(body_len)
        if len(body) != body_len:
            return error(HTTPStatus.BAD_REQUEST, "incomplete request body")
        return body

    @staticmethod
    def _multipart_value(form: cgi.FieldStorage, name: str, default: str) -> str:
        if name not in form:
            return default
        value = form[name].value
        if value is None:
            return default
        return str(value)

    @staticmethod
    def _parse_bool(value: str) -> bool | None:
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return None

    def log_message(self, format: str, *args: Any) -> None:
        super().log_message(format, *args)

    def _send_error(self, response: ErrorResponse) -> None:
        self._send_json(response.status, response.payload)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
