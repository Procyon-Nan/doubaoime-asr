from __future__ import annotations

import argparse
from urllib import error, request


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Call the health endpoint")
    parser.add_argument("--host", default="118.25.74.121")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--path", default="/healthz")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    url = f"http://{args.host}:{args.port}{args.path}"
    try:
        with request.urlopen(url, timeout=10) as resp:
            print(resp.status)
            print(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        print(exc.code)
        print(exc.read().decode("utf-8"))


if __name__ == "__main__":
    main()
