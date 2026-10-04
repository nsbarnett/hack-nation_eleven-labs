"""Bind port zero before announcing readiness; token arrives through stdin, not argv."""
import json
import socket
import sys
import uvicorn
from backend.server import create_app


def main():
    configuration = json.loads(sys.stdin.readline())
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    application = create_app(configuration["root"], configuration["token"])
    server = uvicorn.Server(uvicorn.Config(application, log_level="warning", access_log=False))
    print(json.dumps({"port": listener.getsockname()[1]}), flush=True)
    server.run(sockets=[listener])


if __name__ == "__main__":
    main()
