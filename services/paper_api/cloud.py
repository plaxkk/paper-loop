"""Run API and Worker together on one persistent-disk cloud instance."""
import os
import signal
import subprocess
import sys
import time

from .config import Settings
from .db import initialize


def supervise(commands, shutdown_timeout=20):
    children = []
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        for command in commands:
            children.append(subprocess.Popen(command))
        while not stopping:
            if any(child.poll() is not None for child in children):
                # Fail the whole instance so the platform restarts both processes.
                return 1
            time.sleep(0.2)
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        deadline = time.monotonic() + shutdown_timeout
        for child in children:
            try:
                child.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main():
    port = int(os.getenv("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535")
    initialize(Settings())
    return supervise([
        [sys.executable, "-m", "uvicorn", "services.paper_api.app:app", "--host", "0.0.0.0", "--port", str(port), "--no-access-log"],
        [sys.executable, "-m", "services.paper_api.worker"],
    ])


if __name__ == "__main__":
    raise SystemExit(main())
