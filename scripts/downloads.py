"""Small downloader for the public Census and NCES files."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

USER_AGENT = "Find-a-TVI-Near-Me/1.0 (educational directory)"


def fetch_bytes(url: str, timeout: int = 120) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(fetch_bytes(url))


def fetch_json(url: str, timeout: int = 120) -> dict[str, object]:
    payload = json.loads(fetch_bytes(url, timeout=timeout))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object from {url}")
    return payload
