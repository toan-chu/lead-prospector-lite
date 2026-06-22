from __future__ import annotations

import re
from typing import Any


def normalize_linkedin_profile_url(value: Any, *, with_scheme: bool = False) -> str:
    """Normalize LinkedIn profile URLs so country hosts dedupe and export consistently."""
    url = str(value or "").strip()
    if not url:
        return ""
    url = re.sub(r"^https?://", "", url, flags=re.IGNORECASE)
    url = re.sub(r"^www\.", "", url, flags=re.IGNORECASE)
    url = re.sub(r"^[a-z]{2,3}\.linkedin\.com", "linkedin.com", url, flags=re.IGNORECASE)
    url = url.rstrip("/")
    normalized = url.lower()
    return f"https://{normalized}" if with_scheme and normalized else normalized

