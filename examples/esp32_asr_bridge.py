"""
ESP32 -> Doubao ASR HTTP bridge.

用途：
- 接收来自 ESP32 的整段 PCM 音频
- 调用 doubaoime-asr 做一次性识别
- 仅返回最终文本 JSON

默认接口：
- POST /asr/transcribe
- Content-Type: application/octet-stream
- body: 16kHz / mono / pcm_s16le 原始字节流
"""

from __future__ import annotations

import argparse
import asyncio
import json
import struct
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from doubaoime_asr import ASRConfig, ASRError, ResponseType, transcribe_stream


async def _transcribe_with_log(
    audio_data: bytes,
    config: ASRConfig,
    device_id: str,
) -> str:
    """
    用 transcribe_stream 逐条打印 API 响应，累积所有 FINAL_RESULT 文本。

    相比直接调用 transcribe()，这里能看到每一段的识别过程，
    并且正确拼接多句话的结果（transcribe() 只保留最后一条 FINAL_RESULT，
    多句话时会丢失前面所有段落）。
    """
    # PCM 音频统计：快速确认幅度是否正常
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

    # 逐条响应打印，累积所有最终段落
    final_parts: list[str] = []
    async for resp in transcribe_stream(audio_data, config=config, realtime=True):
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
    return result


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "MiniLunaASRBridge/0.1"

    def do_POST(self) -> None:
        if self.path != self.server.bridge_path:
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return

        content_length = self.headers.get("Content-Length", "0")
        try:
            body_len = int(content_length)
        except ValueError:
            self._send_json(
                HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid content length"}
            )
            return

        if body_len <= 0:
            self._send_json(
                HTTPStatus.BAD_REQUEST, {"ok": False, "error": "empty audio body"}
            )
            return
        if body_len > self.server.max_body_bytes:
            self._send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"ok": False, "error": "audio too large"},
            )
            return

        audio_data = self.rfile.read(body_len)
        if len(audio_data) != body_len:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "incomplete request body"},
            )
            return

        sample_rate = self.headers.get("X-Sample-Rate", "16000")
        channels = self.headers.get("X-Channels", "1")
        audio_format = self.headers.get("X-Audio-Format", "pcm_s16le")
        device_id = self.headers.get("X-Device-Id", "unknown")

        if audio_format != "pcm_s16le":
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "unsupported audio format"},
            )
            return

        try:
            config = ASRConfig(
                credential_path=self.server.credential_path,
                sample_rate=int(sample_rate),
                channels=int(channels),
                enable_punctuation=True,
            )
            text = asyncio.run(_transcribe_with_log(audio_data, config, device_id))
        except ASRError as exc:
            self.log_error("ASR failed for device %s: %s", device_id, exc)
            self._send_json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001
            self.log_error("Unexpected error for device %s: %s", device_id, exc)
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": "internal server error"},
            )
            return

        self.log_message("ASR success for %s: %r", device_id, text)
        self._send_json(HTTPStatus.OK, {"ok": True, "text": text})

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send_json(
                HTTPStatus.OK, {"ok": True, "service": "doubaoime-asr-bridge"}
            )
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def log_message(self, format: str, *args: Any) -> None:
        super().log_message(format, *args)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class BridgeServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        credential_path: str,
        bridge_path: str,
        max_body_bytes: int,
    ):
        super().__init__(server_address, BridgeHandler)
        self.credential_path = credential_path
        self.bridge_path = bridge_path
        self.max_body_bytes = max_body_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description="ESP32 Doubao ASR bridge")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--path", default="/asr/transcribe")
    parser.add_argument("--credential-path", default="./credentials.json")
    parser.add_argument("--max-body-bytes", type=int, default=320000)
    args = parser.parse_args()

    server = BridgeServer(
        (args.host, args.port),
        credential_path=args.credential_path,
        bridge_path=args.path,
        max_body_bytes=args.max_body_bytes,
    )
    print(f"[bridge] listening on http://{args.host}:{args.port}{args.path}")
    print(f"[bridge] credential path: {args.credential_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[bridge] shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
