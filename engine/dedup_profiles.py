from __future__ import annotations

from typing import Any

from engine.url_utils import normalize_linkedin_profile_url


def _norm_url(value: Any) -> str:
    return normalize_linkedin_profile_url(value)


def dedup_profiles(profiles: list[dict]) -> list[dict]:
    """Remove duplicate LinkedIn URLs within the current batch."""
    batch_seen: set[str] = set()
    deduped: list[dict] = []
    for profile in profiles:
        url = _norm_url(profile.get("url") or profile.get("LinkedIn URL") or profile.get("linkedin_url"))
        if not url or url in batch_seen:
            continue
        batch_seen.add(url)
        deduped.append(profile)
    return deduped

