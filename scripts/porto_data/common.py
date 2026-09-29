"""Shared plumbing for the Porto data pipeline: HTTP + raw cache, atomic writes, hashing.

Python 3.10+, standard library only.
"""

from datetime import datetime, timezone
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Callable
import urllib.error
import urllib.request


DEFAULT_USER_AGENT = "porto-parking-heatmap data pipeline (+https://github.com/TheRockPusher/porto-parking-heatmap)"
BACKOFF_SECONDS = 2.0


class DataError(ValueError):
    """An upstream source cannot safely become a published dataset."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def content_hash(data: bytes) -> str:
    """First 10 hex characters of the SHA-256 digest."""
    return hashlib.sha256(data).hexdigest()[:10]


def round_coords(value, digits: int = 6):
    """Recursively round floats inside nested lists (GeoJSON coordinates)."""
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, (list, tuple)):
        return [round_coords(item, digits) for item in value]
    return value


def dumps_compact(obj) -> bytes:
    """Compact UTF-8 JSON with a trailing newline; NaN/Infinity raise ValueError."""
    return (json.dumps(obj, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write via a same-directory temp file, fsync, then os.replace. Temp is cleaned on error."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o644)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _reject_constant(value):
    raise DataError(f"Non-finite JSON number: {value}")


def _finite_float(text):
    number = float(text)
    if not math.isfinite(number):
        raise DataError(f"Non-finite JSON number: {text}")
    return number


class Fetcher:
    """HTTP client with an optional raw-response cache and an offline mode.

    Cache key is sha256(url + body). Online fetches always hit the network and
    rewrite the cache; offline mode reads only the cache and fails on a miss.
    `opener` and `sleep` are injectable so tests need neither network nor waiting.
    """

    def __init__(self, cache_dir: Path | None = None, offline: bool = False,
                 user_agent: str = DEFAULT_USER_AGENT, *,
                 opener: Callable[..., Any] = urllib.request.urlopen,
                 sleep: Callable[[float], None] = time.sleep):
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.offline = offline
        self.user_agent = user_agent
        self._opener = opener
        self._sleep = sleep

    def _cache_key(self, url: str, data: bytes | None) -> str:
        digest = hashlib.sha256(url.encode("utf-8"))
        if data:
            digest.update(data)
        return digest.hexdigest()

    def get_bytes(self, url: str, *, data: bytes | None = None, headers: dict | None = None,
                  timeout: float = 120, retries: int = 3) -> bytes:
        key = self._cache_key(url, data)
        cached = self.cache_dir / f"{key}.bin" if self.cache_dir is not None else None
        if self.offline:
            if cached is None or not cached.is_file():
                raise DataError(f"Offline mode: no cached response for {url}")
            return cached.read_bytes()

        request_headers = {"User-Agent": self.user_agent, "Accept": "application/json, */*"}
        if data is not None:
            request_headers["Content-Type"] = "application/x-www-form-urlencoded"
        request_headers.update(headers or {})
        request = urllib.request.Request(url, data=data, headers=request_headers,
                                         method="POST" if data is not None else "GET")
        body = self._fetch_with_retries(request, url, timeout, retries)
        if cached is not None:
            atomic_write_bytes(cached, body)
            atomic_write_bytes(cached.with_suffix(".url"), url.encode("utf-8"))
        return body

    def _fetch_with_retries(self, request, url: str, timeout: float, retries: int) -> bytes:
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            if attempt:
                self._sleep(BACKOFF_SECONDS * 2 ** (attempt - 1))
            try:
                with self._opener(request, timeout=timeout) as response:
                    return response.read()
            except urllib.error.HTTPError as exc:
                if exc.code != 429 and not 500 <= exc.code < 600:
                    raise DataError(f"HTTP {exc.code} from {url}") from exc
                last_error = exc
            except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException, OSError) as exc:
                last_error = exc
        raise DataError(f"Cannot retrieve {url} after {retries + 1} attempts: {last_error}") from last_error

    def get_json(self, url: str, **kwargs) -> Any:
        body = self.get_bytes(url, **kwargs)
        try:
            return json.loads(body.decode("utf-8-sig"), parse_constant=_reject_constant, parse_float=_finite_float)
        except (UnicodeError, ValueError) as exc:  # DataError is a ValueError
            if isinstance(exc, DataError):
                raise DataError(f"Invalid JSON from {url}: {exc}") from exc
            raise DataError(f"Cannot parse valid JSON from {url}: {exc}") from exc
