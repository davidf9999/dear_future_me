# app/clients/api_client.py
from __future__ import annotations

from typing import Any, Dict, Optional

import httpx  # For both sync and async clients

# You might want to move cfg loading here if both clients need it,
# or pass it in during instantiation. For now, let's assume
# settings are accessed where needed or passed.
# from app.core.settings import get_settings
# cfg = get_settings()


class AsyncAPI:
    """Asynchronous wrapper around the HTTP endpoints."""

    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self._token: Optional[str] = token
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def _post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        _headers = headers or {}
        if self._token:
            _headers["Authorization"] = f"Bearer {self._token}"
        resp = await self._client.post(url, json=json, data=data, headers=_headers)
        resp.raise_for_status()
        return resp

    async def login(self, email: str, password: str) -> str:  # Return type hint
        form = {"username": email, "password": password}
        r = await self._post("/auth/login", data=form)
        try:
            token_value = r.json()["access_token"]
            if not isinstance(token_value, str):
                raise ValueError("Access token received is not a string.")
            self._token = token_value
            return self._token
        except KeyError:
            raise ValueError("Access token not found in login response.")
        except TypeError:  # If r.json() is not a dict or access_token is not subscriptable
            raise ValueError("Invalid login response format.")

    async def register(
        self, email: str, password: str, first_name: str = "API", last_name: str = "User"
    ) -> None:  # Return type hint
        payload = {"email": email, "password": password, "first_name": first_name, "last_name": last_name}
        await self._post("/auth/register", json=payload)
        # No token returned by register, user needs to login after

    async def chat(self, message: str) -> str:
        if not self._token:
            # Consider a custom exception or specific handling
            raise Exception("AsyncAPI: Not authenticated for chat")
        r = await self._post("/chat/text", json={"message": message})
        data = r.json()
        answer = data.get("answer") or data.get("reply")
        if answer is None:
            raise RuntimeError(f"AsyncAPI: Unexpected response payload: {data}")
        return answer

    async def close(self) -> None:
        await self._client.aclose()


class SyncAPI:
    """Synchronous wrapper around the HTTP endpoints."""

    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self._token: Optional[str] = token
        self._client = httpx.Client(timeout=30.0, follow_redirects=True)

    def _post(
        self,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,  # Renamed for clarity vs async version
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        _headers = headers or {}
        if self._token:
            _headers["Authorization"] = f"Bearer {self._token}"
        resp = self._client.post(url, json=json_data, data=data, headers=_headers)
        resp.raise_for_status()
        return resp

    def login(self, email: str, password: str) -> str:  # Return type hint
        form = {"username": email, "password": password}
        r = self._post("/auth/login", data=form)
        try:
            token_value = r.json()["access_token"]
            if not isinstance(token_value, str):
                raise ValueError("Access token received is not a string.")
            self._token = token_value
            return self._token
        except KeyError:
            raise ValueError("Access token not found in login response.")
        except TypeError:  # If r.json() is not a dict or access_token is not subscriptable
            raise ValueError("Invalid login response format.")

    def register(
        self, email: str, password: str, first_name: str = "API", last_name: str = "User"
    ) -> None:  # Return type hint
        payload = {"email": email, "password": password, "first_name": first_name, "last_name": last_name}
        self._post("/auth/register", json_data=payload)
        # No token returned by register, user needs to login after

    def chat(self, message: str) -> str:
        if not self._token:
            # Consider a custom exception or specific handling
            raise Exception("SyncAPI: Not authenticated for chat")
        r = self._post("/chat/text", json_data={"message": message})
        data = r.json()
        answer = data.get("answer") or data.get("reply")
        if answer is None:
            raise RuntimeError(f"SyncAPI: Unexpected response payload: {data}")
        return answer

    def close(self) -> None:
        self._client.close()
