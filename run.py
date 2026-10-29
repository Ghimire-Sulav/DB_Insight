from __future__ import annotations

import logging
import os
import socket
import ipaddress
from pathlib import Path

from waitress import serve

from insightsql import create_app


def main() -> None:
    app = create_app()
    host = os.environ.get("INSIGHTSQL_HOST", "127.0.0.1")
    if not _is_loopback(host):
        raise SystemExit(
            "InsightSQL only supports loopback binding. Do not expose this "
            "unauthenticated local application to a network."
        )
    try:
        port = int(os.environ.get("INSIGHTSQL_PORT", "5000"))
    except ValueError as error:
        raise SystemExit("INSIGHTSQL_PORT must be an integer.") from error
    if not 1 <= port <= 65535:
        raise SystemExit("INSIGHTSQL_PORT must be between 1 and 65535.")

    Path(app.config["HISTORY_PATH"]).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO)
    app.logger.info("Starting InsightSQL on http://%s:%s", host, port)
    serve(app, host=host, port=port, threads=4, clear_untrusted_proxy_headers=True)


def _is_loopback(host: str) -> bool:
    try:
        return all(
            ipaddress.ip_address(address[4][0]).is_loopback
            for address in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        )
    except (OSError, ValueError):
        return False


if __name__ == "__main__":
    main()
