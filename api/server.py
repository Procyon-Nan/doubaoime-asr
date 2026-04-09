from __future__ import annotations

from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path

from .service import ASRService


SECRET_KEY_PATH = Path(__file__).resolve().parent.parent / "secret_key"
DEFAULT_ALIYUN_SECRET_KEY = "1145141919810"


def load_aliyun_secret_key() -> str:
    if not SECRET_KEY_PATH.exists():
        return DEFAULT_ALIYUN_SECRET_KEY
    return SECRET_KEY_PATH.read_text(encoding="utf-8").strip() or DEFAULT_ALIYUN_SECRET_KEY


@dataclass(slots=True)
class ServerOptions:
    host: str = "0.0.0.0"
    port: int = 9000
    bridge_path: str = "/asr/transcribe"
    standard_path: str = "/v1/stt/transcriptions"
    aliyun_path: str = "/stream/v1/asr"
    aliyun_secret_key: str = load_aliyun_secret_key()
    health_path: str = "/healthz"
    credential_path: str = "./credentials.json"
    max_body_bytes: int = 320000
    service_name: str = "doubaoime-asr-api"


class ASRHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class, options: ServerOptions):
        super().__init__(server_address, handler_class)
        self.options = options
        self.service = ASRService(options.credential_path)
