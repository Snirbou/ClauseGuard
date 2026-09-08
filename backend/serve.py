"""Container entrypoint: serve the API on IPv4 *and* IPv6 at $PORT.

Why not plain ``uvicorn --host``: asyncio's ``create_server`` sets
``IPV6_V6ONLY`` on ``::`` sockets, so ``--host ::`` accepts IPv6 only, while
``--host 0.0.0.0`` accepts IPv4 only. Railway's private network reaches the
API over IPv6 (``api.railway.internal``) whereas docker-compose, Docker's
port proxy and public edges connect over IPv4 — so the container binds both
families explicitly and hands the listening sockets to uvicorn.

Local development keeps using ``uvicorn main:app --port 8000`` directly.
"""

from __future__ import annotations

import os
import socket
import sys

import uvicorn

DEFAULT_PORT = 8000
BACKLOG = 2048


def bind(family: int, address: str, port: int) -> socket.socket:
    """Return a listening socket for one address family."""
    sock = socket.socket(family, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if family == socket.AF_INET6:
        # Keep the IPv6 socket IPv6-only; the IPv4 socket owns 0.0.0.0.
        # Without this, binding both would conflict on dual-stack kernels.
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
    sock.bind((address, port))
    sock.listen(BACKLOG)
    sock.set_inheritable(True)
    return sock


def listening_sockets(port: int) -> list[socket.socket]:
    sockets = [bind(socket.AF_INET, "0.0.0.0", port)]
    try:
        sockets.append(bind(socket.AF_INET6, "::", port))
    except OSError as exc:  # IPv6 disabled in this network namespace
        print(f"[serve] IPv6 listener unavailable ({exc}); serving IPv4 only.", flush=True)
    return sockets


def main() -> int:
    port = int(os.environ.get("PORT", str(DEFAULT_PORT)))
    sockets = listening_sockets(port)
    families = ", ".join(
        "[::]" if s.family == socket.AF_INET6 else "0.0.0.0" for s in sockets
    )
    print(f"[serve] listening on {families} port {port}", flush=True)

    config = uvicorn.Config("main:app", port=port, log_level="info")
    uvicorn.Server(config).run(sockets=sockets)
    return 0


if __name__ == "__main__":
    sys.exit(main())
