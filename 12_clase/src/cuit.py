"""CUIT lookup against the Supabase (PostgREST) table."""

import json
import re

import httpx

from src.config import Settings

CUIT_PATTERN = re.compile(r"\b\d{2}-?\d{8}-?\d\b")


def extract_cuit(text: str) -> str | None:
    """Return the first CUIT found in `text` as 11 digits, or None."""
    match = CUIT_PATTERN.search(text)
    return re.sub(r"\D", "", match.group()) if match else None


class CuitClient:
    def __init__(self, http: httpx.Client, table: str) -> None:
        self.http = http
        self.table = table

    def lookup(self, cuit: str) -> dict | None:
        response = self.http.get(f"/{self.table}", params={"cuit": f"eq.{cuit}", "limit": 1})
        response.raise_for_status()
        rows = response.json()
        return rows[0] if rows else None


def describe_cuit(client: CuitClient, cuit: str) -> str:
    """JSON with the fiscal data, or an error the LLM can explain to the user."""
    digits = re.sub(r"\D", "", cuit)
    if len(digits) != 11:
        return _error("CUIT must have 11 digits")
    try:
        row = client.lookup(digits)
    except httpx.HTTPError as exc:
        return _error(f"CUIT service unavailable: {exc}")
    return json.dumps(row, ensure_ascii=False) if row else _error("CUIT not found")


def _error(message: str) -> str:
    return json.dumps({"error": message}, ensure_ascii=False)


def build_cuit_client(settings: Settings) -> CuitClient:
    key = settings.secrets.supabase_key.get_secret_value()
    http = httpx.Client(
        base_url=f"{settings.supabase.url.rstrip('/')}/rest/v1",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=settings.supabase.timeout_seconds,
    )
    return CuitClient(http, settings.supabase.table)
