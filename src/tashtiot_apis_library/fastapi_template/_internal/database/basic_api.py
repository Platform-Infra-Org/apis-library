import httpx
from typing import Optional, Dict, Tuple

from httpx import AsyncClient


class BaseAPI:
    def __init__(
        self,
        base_url: str,
        headers: Optional[Dict[str, str]] = None,
        auth: Optional[Tuple[str, str]] = None,
        timeout: float = 10.0,
        verify: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.auth = auth
        self.timeout = timeout
        self.verify = verify
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Return an AsyncClient.

        - Inside `async with`: returns the reusable client.
        - Outside: returns a temporary client you can `async with`.
        """
        if self._client:
            return self._client
        # Outside context: return a temporary client (must be used with `async with`)
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout,
            verify=self.verify,
            auth=self.auth,
        )

    # Context manager
    async def __aenter__(self) -> AsyncClient:
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout,
            verify=self.verify,
            auth=self.auth,
        )
        return self._client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
            self._client = None
