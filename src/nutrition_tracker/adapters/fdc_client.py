"""USDA FoodData Central API client."""

from dataclasses import dataclass
from typing import Protocol

import httpx


class FdcClient(Protocol):
    """Interface for FoodData Central API interactions."""

    async def search_foods(self, query: str, page_size: int = 10) -> dict[str, object]:
        """Search foods by query and return raw API data."""

    async def get_food(self, fdc_id: int) -> dict[str, object]:
        """Fetch a food by FDC id and return raw API data."""


@dataclass
class HttpxFdcClient(FdcClient):
    """HTTPX-backed FDC client."""

    api_key: str
    base_url: str
    http_client: httpx.AsyncClient

    @classmethod
    def create(cls, api_key: str, base_url: str) -> "HttpxFdcClient":
        """Create an FDC client with a managed httpx session."""
        return cls(api_key=api_key, base_url=base_url, http_client=httpx.AsyncClient())

    async def search_foods(self, query: str, page_size: int = 10) -> dict[str, object]:
        """Search foods by query."""
        url = f"{self.base_url}/foods/search"
        response = await self.http_client.post(
            url,
            params={"api_key": self.api_key},
            json={"query": query, "pageSize": page_size},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    async def get_food(self, fdc_id: int) -> dict[str, object]:
        """Fetch a food by FDC id."""
        url = f"{self.base_url}/food/{fdc_id}"
        response = await self.http_client.get(
            url,
            params={"api_key": self.api_key},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        await self.http_client.aclose()
