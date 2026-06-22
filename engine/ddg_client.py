"""DuckDuckGo search client using urllib only."""

from __future__ import annotations

import logging
import random
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

logger = logging.getLogger("ddg_client")


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

BLOCK_MARKERS = [
    "anomaly detected",
    "bots use duckduckgo too",
    "rate limit",
    "too many requests",
    "challenge-form",
    "captcha",
]


class DDGBlocked(RuntimeError):
    """DuckDuckGo returned a network error or challenge page."""


class DDGEmpty(RuntimeError):
    """DuckDuckGo explicitly returned no results."""


def search(
    query: str,
    timeout: int = 30,
    min_delay: float = 2.0,
    max_delay: float = 4.0,
) -> str:
    """Return the DuckDuckGo HTML result page for a query."""
    time.sleep(random.uniform(min_delay, max_delay))
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    request = Request(
        url,
        headers={
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
        },
    )
    logger.warning("DDG fetch start url=%s query=%s", url, query[:80])
    try:
        html = urlopen(request, timeout=timeout).read().decode("utf-8", "replace")
    except HTTPError as exc:
        logger.error("DDG HTTPError status=%s reason=%s url=%s", exc.code, exc.reason, url)
        raise DDGBlocked(f"HTTP {exc.code} {exc.reason}") from exc
    except URLError as exc:
        logger.error("DDG URLError reason=%s url=%s", exc.reason, url)
        raise DDGBlocked(f"Network error: {exc.reason}") from exc

    logger.warning("DDG fetch ok bytes=%d", len(html))
    lower = html.lower()
    matched_marker = next((marker for marker in BLOCK_MARKERS if marker in lower), None)
    if matched_marker:
        logger.error("DDG block marker matched=%s", matched_marker)
        raise DDGBlocked(f"DuckDuckGo block/challenge page detected (marker={matched_marker})")
    if "no results" in lower or 'data-testid="no-results"' in lower:
        logger.warning("DDG returned no-results page")
        raise DDGEmpty("No results from DuckDuckGo")
    return html
