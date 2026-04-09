from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from urllib import error, request


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Test legacy and standard STT APIs")
    parser.add_argument("audio", help="PCM s16le raw audio file path")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--legacy-path", default="/asr/transcribe")
    parser.add_argument("--standard-path", default="/v1/stt/transcriptions")
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--channels", type=int, default=1)
    parser.add_argument("--audio-format", default="pcm_s16le")
    parser.add_argument("--device-id", default="test-client")
    parser.add_argument("--multipart", action="store_true", help="Use multipart/form-data for standard API")
    return parser


def post_json(url: str, payload: dict) -> tuple[int, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return fetch(req)


def post_binary(url: str, audio_data: bytes, *, sample_rate: int, channels: int, audio_format: str, device_id: str) -> tuple[int, str]:
    req = request.Request(
        url,
        data=audio_data,
        headers={
            "Content-Type": "application/octet-stream",
            "X-Sample-Rate": str(sample_rate),
            "X-Channels": str(channels),
            "X-Audio-Format": audio_format,
            "X-Device-Id": device_id,
        },
        method="POST",
    )
    return fetch(req)


def post_multipart(url: str, audio_data: bytes, *, sample_rate: int, channels: int, audio_format: str, device_id: str) -> tuple[int, str]:
    boundary = "----DoubaoASRBoundary7MA4YWxkTrZu0gW"
    body = b"".join([
        field(boundary, "format", audio_format),
        field(boundary, "sample_rate", str(sample_rate)),
        field(boundary, "channels", str(channels)),
        field(boundary, "device_id", device_id),
        field(boundary, "enable_punctuation", "true"),
        field(boundary, "realtime", "true"),
        file_field(boundary, "file", "audio.pcm", "application/octet-stream", audio_data),
        f"--{boundary}--\r\n".encode("utf-8"),
    ])
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    return fetch(req)


def field(boundary: str, name: str, value: str) -> bytes:
    return (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
        f"{value}\r\n"
    ).encode("utf-8")


def file_field(boundary: str, name: str, filename: str, content_type: str, data: bytes) -> bytes:
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8")
    return header + data + b"\r\n"


def fetch(req: request.Request) -> tuple[int, str]:
    try:
        with request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def main() -> None:
    args = build_parser().parse_args()
    audio_path = Path(args.audio)
    audio_data = audio_path.read_bytes()
    base_url = f"http://118.25.74.121:{args.port}"

    legacy_status, legacy_body = post_binary(
        f"{base_url}{args.legacy_path}",
        audio_data,
        sample_rate=args.sample_rate,
        channels=args.channels,
        audio_format=args.audio_format,
        device_id=args.device_id,
    )
    print("=== Legacy API ===")
    print(legacy_status)
    print(legacy_body)
    print()

    if args.multipart:
        standard_status, standard_body = post_multipart(
            f"{base_url}{args.standard_path}",
            audio_data,
            sample_rate=args.sample_rate,
            channels=args.channels,
            audio_format=args.audio_format,
            device_id=args.device_id,
        )
        mode = "multipart/form-data"
    else:
        standard_status, standard_body = post_json(
            f"{base_url}{args.standard_path}",
            {
                "audio": {
                    "content_base64": base64.b64encode(audio_data).decode("ascii"),
                    "format": args.audio_format,
                    "sample_rate": args.sample_rate,
                    "channels": args.channels,
                },
                "options": {
                    "enable_punctuation": True,
                    "realtime": True,
                },
                "device_id": args.device_id,
            },
        )
        mode = "application/json"

    print(f"=== Standard API ({mode}) ===")
    print(standard_status)
    print(standard_body)


if __name__ == "__main__":
    main()
