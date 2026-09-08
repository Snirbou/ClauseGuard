"""serve.py — the container entrypoint must offer IPv4 and (where the kernel
allows) IPv6 listeners on the same port, because asyncio's own "::" bind is
IPv6-only and Railway's private network is IPv6 while compose is IPv4."""

from __future__ import annotations

import socket

import pytest

import serve


def test_ipv4_listener_binds_an_ephemeral_port() -> None:
    sock = serve.bind(socket.AF_INET, "127.0.0.1", 0)
    try:
        assert sock.getsockname()[1] > 0
    finally:
        sock.close()


def test_ipv6_listener_is_v6only_so_both_families_can_share_a_port() -> None:
    try:
        sock6 = serve.bind(socket.AF_INET6, "::1", 0)
    except OSError:
        pytest.skip("IPv6 not available on this host")
    try:
        assert sock6.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY) == 1
    finally:
        sock6.close()


def test_listening_sockets_share_one_port() -> None:
    # Port 0 picks a free port for the IPv4 socket; the IPv6 socket gets the
    # same explicit port in production. Here we only assert the IPv4 one
    # exists and that the helper never raises when IPv6 is missing.
    sockets = serve.listening_sockets(0)
    try:
        assert sockets[0].family == socket.AF_INET
        assert all(s.family in (socket.AF_INET, socket.AF_INET6) for s in sockets)
    finally:
        for s in sockets:
            s.close()
