import os
import shutil
import subprocess
import sys
import time
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest
import pytest_asyncio
from playwright.async_api import BrowserContext, async_playwright

from app.auth.jwt import create_access_token
from app.models import User
from tests.membership_support import MembershipDatabase

BACKEND_PORT = int(os.environ.get("TEST_BACKEND_PORT", "8126"))
FRONTEND_PORT = int(os.environ.get("TEST_FRONTEND_PORT", "5176"))
BASE_URL = f"http://127.0.0.1:{FRONTEND_PORT}"


@pytest.fixture(scope="session")
def servers(tmp_path_factory) -> Generator[str, None, None]:
    """Own only these two local server PIDs; no app-side authentication bypass."""
    root = Path(__file__).resolve().parents[1]
    logs = tmp_path_factory.mktemp("invite-servers")
    env = os.environ.copy()
    env["ENVIRONMENT"] = "development"
    env["VITE_BACKEND_URL"] = f"http://127.0.0.1:{BACKEND_PORT}"
    # Validate the DB target before any server or data mutation.
    MembershipDatabase()
    for port in (BACKEND_PORT, FRONTEND_PORT):
        import socket

        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(f"Test port {port} is already in use")
    processes = []
    with (
        (logs / "backend.log").open("w") as backend_log,
        (logs / "frontend.log").open("w") as frontend_log,
    ):
        try:
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "app.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(BACKEND_PORT),
                        "--no-access-log",
                    ],
                    cwd=root,
                    env=env,
                    stdout=backend_log,
                    stderr=subprocess.STDOUT,
                )
            )
            node = shutil.which("node")
            if not node:
                raise RuntimeError("Node is required for browser regressions")
            processes.append(
                subprocess.Popen(
                    [
                        node,
                        str(
                            root.parent
                            / "frontend"
                            / "node_modules"
                            / "vite"
                            / "bin"
                            / "vite.js"
                        ),
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(FRONTEND_PORT),
                        "--strictPort",
                    ],
                    cwd=root.parent / "frontend",
                    env=env,
                    stdout=frontend_log,
                    stderr=subprocess.STDOUT,
                )
            )
            for url in (
                f"http://127.0.0.1:{BACKEND_PORT}/api/v1/health",
                BASE_URL,
            ):
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    if any(process.poll() is not None for process in processes):
                        raise RuntimeError(f"Test server exited; inspect {logs}")
                    try:
                        with urlopen(url, timeout=2) as response:
                            if response.status == 200:
                                break
                    except (URLError, TimeoutError):
                        time.sleep(0.2)
                else:
                    raise RuntimeError(f"Test server not ready: {url}; inspect {logs}")
            yield BASE_URL
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


@pytest_asyncio.fixture
async def real_db() -> AsyncGenerator[MembershipDatabase, None]:
    async with MembershipDatabase() as database:
        yield database


@pytest_asyncio.fixture
async def context(servers: str) -> AsyncGenerator[BrowserContext, None]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(base_url=servers)
        yield context
        await context.close()
        await browser.close()


async def authenticate(context: BrowserContext, user: User) -> None:
    """Mint test identities outside the app, never add a production login route."""
    await context.add_cookies(
        [
            {
                "name": "access_token",
                "value": create_access_token(user.id),
                "url": BASE_URL,
                "httpOnly": True,
                "sameSite": "Lax",
            }
        ]
    )
