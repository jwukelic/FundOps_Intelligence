import hashlib
import requests


def fetch_public_url_text(url: str, timeout_seconds: int = 15) -> tuple[str, str]:
    response = requests.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    text = response.text[:20000]
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()
