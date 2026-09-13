"""Dual-stack entry: one listener serving 127.0.0.1, ::1, and localhost on :8000.
Uvicorn's --host ::/0.0.0.0 each answer only one family on macOS; this clears V6ONLY."""
import socket
import uvicorn

s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
s.bind(("::", 8000))
s.listen(128)
uvicorn.run("app:app", fd=s.fileno(), log_level="info")
