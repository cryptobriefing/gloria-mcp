"""Async HTTP client wrapping the ai-hub API."""

import httpx


class GloriaClient:
    """Thin async wrapper around ai-hub REST endpoints."""

    def __init__(self, base_url: str, token: str):
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._http: httpx.AsyncClient | None = None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=30.0,
            )
        return self._http

    async def _get(self, path: str, params: dict | None = None) -> dict | list:
        client = await self._client()
        params = params or {}
        params["token"] = self._token
        resp = await client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_news(
        self,
        category: str | None = None,
        keyword: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        params: dict = {"limit": limit, "page": 1}
        if category:
            params["feed_categories"] = category
        if keyword:
            params["keyword"] = keyword
        return await self._get("/news", params)

    async def get_news_by_id(self, news_id: str) -> dict:
        return await self._get(f"/news/{news_id}")

    async def get_recap(self, category: str, timeframe: str = "12h") -> dict:
        return await self._get("/recaps", {
            "feed_category": category,
            "timeframe": timeframe,
        })

    async def get_categories(self) -> list[dict]:
        """Public endpoint — no auth needed, but token doesn't hurt."""
        return await self._get("/available-feed-categories")

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()
