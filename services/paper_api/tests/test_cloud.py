import subprocess
import sys
import time


def test_supervisor_stops_sibling_when_worker_exits(tmp_path):
    marker = tmp_path / "stopped"
    ready = tmp_path / "ready"
    sibling = (
        "import signal,time; from pathlib import Path; "
        f"signal.signal(signal.SIGTERM,lambda *_: (Path({str(marker)!r}).touch(),exit(0))); "
        f"Path({str(ready)!r}).touch(); time.sleep(60)"
    )
    exiting = (
        "import time; from pathlib import Path; "
        f"p=Path({str(ready)!r}); "
        "\nfor _ in range(100):\n if p.exists(): break\n time.sleep(.05)\n"
    )
    source = (
        "from services.paper_api.cloud import supervise; "
        f"raise SystemExit(supervise([[{sys.executable!r},'-c',{sibling!r}],"
        f"[{sys.executable!r},'-c',{exiting!r}]],shutdown_timeout=2))"
    )
    result = subprocess.run([sys.executable, "-c", source], timeout=12)
    assert result.returncode == 1
    assert marker.exists()


def test_supervisor_forwards_shutdown(tmp_path):
    ready = tmp_path / "ready"
    marker = tmp_path / "stopped"
    child = (
        "import signal,time; from pathlib import Path; "
        f"signal.signal(signal.SIGTERM,lambda *_: (Path({str(marker)!r}).touch(),exit(0))); "
        f"Path({str(ready)!r}).touch(); time.sleep(60)"
    )
    source = (
        "from services.paper_api.cloud import supervise; "
        f"raise SystemExit(supervise([[{sys.executable!r},'-c',{child!r}]],shutdown_timeout=2))"
    )
    process = subprocess.Popen([sys.executable, "-c", source])
    try:
        deadline = time.monotonic() + 8
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        assert ready.exists()
        process.terminate()
        assert process.wait(timeout=5) == 0
        assert marker.exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
