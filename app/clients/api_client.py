import json
from typing import Any, Iterator, cast

import httpx
from pydantic import BaseModel

from app.auth.schemas import UserRead  # Assuming UserRead is here for type hinting


class APIError(Exception):
    """Custom exception for API client errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MessagePayload(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    session_id: str | None = None  # Assuming session_id might be part of the response


class SyncAPI:
    """Synchronous client for interacting with the DFM API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, timeout=30.0)
        self.token: str | None = None

    def _handle_response(self, response: httpx.Response) -> Any:
        if not response.is_success:
            try:
                detail = response.json().get("detail", response.text)
            except json.JSONDecodeError:
                detail = response.text
            raise APIError(
                f"API request failed: {response.status_code} - {detail}",
                status_code=response.status_code,
            )
        try:
            return response.json()
        except json.JSONDecodeError:
            return response.text  # Or handle non-JSON responses as needed

    def _get_access_token(self, email: str, password: str) -> str:
        """Authenticates and stores the access token."""
        response = self.client.post("/auth/login", data={"username": email, "password": password})
        # No need to call _handle_response here if we want custom logic for token
        if not response.is_success:
            try:
                detail = response.json().get("detail", response.text)
            except json.JSONDecodeError:
                detail = response.text
            raise APIError(
                f"Login failed: {response.status_code} - {detail}",
                status_code=response.status_code,
            )
        try:
            response_data = response.json()
            if isinstance(response_data, dict) and "access_token" in response_data:
                token_val = response_data["access_token"]
                if isinstance(token_val, str):
                    return token_val
                else:
                    raise APIError(f"Access token received is not a string: {type(token_val)}")
            raise APIError(f"Access token not found in login response: {response_data}")
        except json.JSONDecodeError:
            raise APIError(f"Login response was not valid JSON: {response.text}")

    def login(self, email: str, password: str) -> None:
        self.token = self._get_access_token(email, password)
        self.client.headers["Authorization"] = f"Bearer {self.token}"

    def register(self, email: str, password: str) -> UserRead:
        payload = {"email": email, "password": password, "is_active": True, "is_superuser": False, "is_verified": False}
        response = self.client.post("/auth/register", json=payload)
        data = self._handle_response(response)
        return UserRead(**data)  # Assuming UserRead can be created from the response dict

    def chat(self, message: str) -> ChatResponse:
        if not self.token:
            raise APIError("Not authenticated. Please login first.")
        response = self.client.post("/chat/text", json={"message": message})
        data = self._handle_response(response)
        return ChatResponse(**data)  # Assuming ChatResponse can be created from the response dict

    def chat_stream(self, message: str) -> Iterator[str]:
        """
        Sends a message to the /chat/stream endpoint and yields response chunks.
        Assumes the stream returns newline-separated JSON objects, each being a string chunk.
        """
        if not self.token:
            raise APIError("Not authenticated. Please login first.")
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/x-ndjson"}
        payload = {"message": message}

        with self.client.stream("POST", "/chat/stream", json=payload, headers=headers) as response:
            if not response.is_success:
                # Attempt to read the error response body
                error_content = "".join([chunk.decode() for chunk in response.iter_bytes()])
                try:
                    detail = json.loads(error_content).get("detail", error_content)
                except json.JSONDecodeError:
                    detail = error_content
                raise APIError(
                    f"API stream request failed: {response.status_code} - {detail}",
                    status_code=response.status_code,
                )
            for line_bytes in response.iter_lines():
                line = line_bytes  # httpx iter_lines already decodes by default
                if line:
                    # Assuming each line is a string chunk directly, not JSON for this example
                    # If each line IS a JSON object like {"chunk": "text"}, adjust parsing:
                    # try:
                    #   data = json.loads(line)
                    #   yield cast(str, data.get("chunk", ""))
                    # except json.JSONDecodeError:
                    #   print(f"Warning: Could not decode JSON line from stream: {line}")
                    yield cast(str, line)

    def logout(self) -> None:
        if not self.token:
            # Optionally, raise an error or just silently pass
            # print("Not logged in, so no logout action taken.")
            return
        try:
            self.client.post("/auth/logout")
        except httpx.RequestError as e:
            # Handle network errors during logout if necessary
            print(f"Network error during logout: {e}")
        finally:
            self.token = None
            if "Authorization" in self.client.headers:
                del self.client.headers["Authorization"]
