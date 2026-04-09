from __future__ import annotations

import argparse

from .handlers import ASRRequestHandler
from .server import ASRHTTPServer, ServerOptions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Doubao ASR API server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--path", default="/asr/transcribe")
    parser.add_argument("--standard-path", default="/v1/stt/transcriptions")
    parser.add_argument("--health-path", default="/healthz")
    parser.add_argument("--credential-path", default="./credentials.json")
    parser.add_argument("--max-body-bytes", type=int, default=320000)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    options = ServerOptions(
        host=args.host,
        port=args.port,
        bridge_path=args.path,
        standard_path=args.standard_path,
        health_path=args.health_path,
        credential_path=args.credential_path,
        max_body_bytes=args.max_body_bytes,
    )
    server = ASRHTTPServer((options.host, options.port), ASRRequestHandler, options)
    print(f"[api] legacy endpoint: http://{options.host}:{options.port}{options.bridge_path}")
    print(f"[api] standard endpoint: http://{options.host}:{options.port}{options.standard_path}")
    print(f"[api] health endpoint: http://{options.host}:{options.port}{options.health_path}")
    print(f"[api] credential path: {options.credential_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[api] shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
