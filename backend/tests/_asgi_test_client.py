from __future__ import annotations

import threading
import time
from typing import Any

import httpx
import uvicorn


class TestClient:
    """Synchronous test client backed by a real local Uvicorn server."""

    __test__ = False

    def __init__(self, app, *, base_url: str = "http://127.0.0.1", **client_options: Any) -> None:
        self.app = app
        self.base_url = base_url
        self.client_options = client_options
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._client: httpx.Client | None = None

    def _ensure_started(self) -> None:
        if self._client is not None:
            return

        probe = __import__("socket").socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()

        config = uvicorn.Config(
            self.app,
            host="127.0.0.1",
            port=port,
            log_level="error",
            access_log=False,
            lifespan="off",
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()

        deadline = time.monotonic() + 10
        while not self._server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        if not self._server.started or not self._server.servers:
            raise RuntimeError("Uvicorn test server failed to start")

        self._client = httpx.Client(
            base_url=f"{self.base_url}:{port}",
            follow_redirects=self.client_options.get("follow_redirects", True),
        )

    def __enter__(self) -> "TestClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._server = None
        self._thread = None

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self._ensure_started()
        assert self._client is not None
        return self._client.request(method, url, **kwargs)

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)
