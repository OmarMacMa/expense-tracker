import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def artifacts(tmp_path_factory):
    path = Path(os.environ.get("CHART_ARTIFACTS", tmp_path_factory.mktemp("charts")))
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture(scope="session")
def chart_server(artifacts):
    """Controlled API rendering needs only Vite, not PostgreSQL or real OAuth."""
    root = Path(__file__).resolve().parents[1]
    port = int(os.environ.get("CHART_TEST_PORT", "5182"))
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"Chart test port {port} is already occupied")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node is required for chart browser regressions")
    with (artifacts / "vite.log").open("w") as log:
        process = subprocess.Popen(
            [
                node,
                str(root / "node_modules" / "vite" / "bin" / "vite.js"),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--strictPort",
            ],
            cwd=root,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            url = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"Vite exited; inspect {artifacts / 'vite.log'}")
                try:
                    with urlopen(url, timeout=2) as response:
                        if response.status == 200:
                            break
                except (URLError, TimeoutError):
                    time.sleep(0.2)
            else:
                raise RuntimeError("Vite did not become ready")
            yield url
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


@pytest.fixture(scope="session")
def browser(chart_server):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        yield browser
        browser.close()
