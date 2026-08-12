from __future__ import annotations

from typing import Protocol

from google.cloud import secretmanager


class SecretProvider(Protocol):
    def get(self, secret_name: str, *, default: str = "") -> str: ...


class GoogleSecretManagerProvider:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self._client = secretmanager.SecretManagerServiceClient() if project_id else None

    def get(self, secret_name: str, *, default: str = "") -> str:
        if not secret_name:
            return default
        if not self._client:
            return default
        resource = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
        response = self._client.access_secret_version(request={"name": resource})
        return response.payload.data.decode("utf-8")


class StaticSecretProvider:
    def __init__(self, values: dict[str, str] | None = None):
        self.values = values or {}

    def get(self, secret_name: str, *, default: str = "") -> str:
        return self.values.get(secret_name, default)

