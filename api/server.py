from __future__ import annotations

from dataclasses import dataclass
from http.server import ThreadingHTTPServer

from .service import ASRService


@dataclass(slots=True)
class ServerOptions:
    host: str = "0.0.0.0"
    port: int = 9000
    bridge_path: str = "/asr/transcribe"
    standard_path: str = "/v1/stt/transcriptions"
    aliyun_path: str = "/stream/v1/asr"
    health_path: str = "/healthz"
    credential_path: str = "./credentials.json"
    max_body_bytes: int = 320000
    service_name: str = "doubaoime-asr-api"


class ASRHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class, options: ServerOptions):
        super().__init__(server_address, handler_class)
        self.options = options
        self.service = ASRService(options.credential_path)
