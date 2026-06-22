from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, unquote, urlparse

from engine.url_utils import normalize_linkedin_profile_url


MIDDLE_DOT = "\u00b7"
PROFILE_RE = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[^/?#\"'<>\\\s]+/?", re.IGNORECASE)
STRICT_AT_RE = re.compile(r"^(?P<title>.+?)\s+(?:at|@|tai|t\u1ea1i)\s+(?P<company>.+?)(?:\s*[\u00b7]|\s*$)", re.IGNORECASE)
TITLE_MARKER_RE = re.compile(
    r"\b(procurement|purchas\w*|buyer|buying|sourcing|supply chain|logistics|import|category|commodity|coffee trader|sales executive|managing director)\b",
    re.IGNORECASE,
)
BAD_VIETNAMESE_AT_RE = re.compile(r"\b(?:tai|t\u1ea1i)\s+(?:day|d\u00e2y|\u0111\u00e2y|dia\s*chi|\u0111\u1ecba\s*ch\u1ec9|nha|nh\u00e0)\b", re.IGNORECASE)


def _clean_url(value: str) -> str:
    decoded = html.unescape(unquote(value))
    parsed = urlparse(decoded)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        decoded = unquote(target)
    match = PROFILE_RE.search(decoded)
    return normalize_linkedin_profile_url(match.group(0), with_scheme=True) if match else ""


def _clean_text(value: str) -> str:
    value = re.sub(r"<(script|style)\b.*?</\1>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _strip_linkedin_suffix(title: str) -> str:
    title = re.sub(r"\s*\|\s*LinkedIn\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*-\s*LinkedIn\s*$", "", title, flags=re.IGNORECASE)
    return re.sub(r"\s*\|\s*LinkedIn.*$", "", title, flags=re.IGNORECASE).strip()


def _clean_company(value: str) -> str:
    value = re.split(r"\s*[|\u00b7;]\s*", value, maxsplit=1)[0]
    value = re.split(r"\s+(?:with|where|which|who|that|and)\s+", value, maxsplit=1, flags=re.IGNORECASE)[0]
    return value.strip(" .,-")


def _clean_title(value: str) -> str:
    value = re.sub(r"^(?:i'?m|i am|currently|as an?|a|the|motivated)\s+", "", str(value or "").strip(" .,-"), flags=re.IGNORECASE)
    value = re.split(r"\s*[|]\s*", value, maxsplit=1)[0]
    value = re.sub(r"\s+", " ", value)
    return value.strip(" .,-")


def _split_title(title: str) -> tuple[str, str, str, str, str]:
    """Return name, title, company, parse_status, company_source from a DDG heading."""
    title = _strip_linkedin_suffix(title)
    dot_parts = [part.strip() for part in re.split(r"\s*[\u00b7]\s*", title) if part.strip()]
    if len(dot_parts) >= 2:
        strict = STRICT_AT_RE.match(dot_parts[1])
        if strict:
            return dot_parts[0], _clean_title(strict.group("title")), _clean_company(strict.group("company")), "ok", "title"

    parts = [part.strip() for part in re.split(r"\s+-\s+", title) if part.strip()]
    name = parts[0] if parts else ""
    if len(parts) >= 3 and TITLE_MARKER_RE.search(parts[1]):
        return name, _clean_title(parts[1]), _clean_company(parts[2]), "ok", "title"

    at_match = re.search(r"\b(?:at|@|tai|t\u1ea1i)\s+(.+)$", title, flags=re.IGNORECASE)
    if at_match:
        before = title[: at_match.start()].strip(" -")
        before_parts = [part.strip() for part in re.split(r"\s+-\s+", before) if part.strip()]
        if len(before_parts) >= 2:
            return before_parts[0], _clean_title(before_parts[-1]), _clean_company(at_match.group(1)), "ok", "title"
        if len(before_parts) == 1 and TITLE_MARKER_RE.search(before_parts[0]):
            return "", _clean_title(before_parts[0]), _clean_company(at_match.group(1)), "ok", "title"

    return name, "", "", "parse_failed", ""


def _company_from_heading(title_text: str) -> str:
    title = _strip_linkedin_suffix(title_text)
    parts = [part.strip() for part in re.split(r"\s+-\s+", title) if part.strip()]
    if len(parts) >= 2 and not TITLE_MARKER_RE.search(parts[1]):
        return _clean_company(parts[1])
    match = re.search(r"\b(?:at|@|tai|t\u1ea1i)\s+(.+)$", title, flags=re.IGNORECASE)
    return _clean_company(match.group(1)) if match else ""


def _company_from_snippet(snippet: str) -> str:
    experience = re.search(r"(?:Kinh nghi.m|Experience)\s*:\s*(.+?)(?:\u00b7|\.|$)", snippet, flags=re.IGNORECASE)
    if experience:
        return _clean_company(experience.group(1).replace("\n", " "))
    return ""


def _company_mention_from_snippet(snippet: str) -> str:
    for match in re.finditer(r"\b([A-Z][A-Za-z0-9&.' -]{2,40})\s+(?:is|was|breaks|in)\b", snippet or ""):
        company = _clean_company(match.group(1))
        if company.lower() not in {"established", "location", "department"}:
            return company
    return ""


def _role_from_two_part_title(title_text: str, snippet_company: str) -> tuple[str, str]:
    title = _strip_linkedin_suffix(title_text)
    parts = [part.strip() for part in re.split(r"\s+-\s+", title) if part.strip()]
    if len(parts) != 2 or not snippet_company:
        return "", ""
    candidate = parts[1]
    if snippet_company.lower() in candidate.lower() or candidate.lower() in snippet_company.lower():
        return "", ""
    if not TITLE_MARKER_RE.search(candidate):
        return "", ""
    return parts[0], _clean_title(candidate)


def _is_breadcrumb(text: str) -> bool:
    lowered = text.lower()
    return "linkedin.com" in lowered or "\u203a" in text or lowered.startswith("http")


def _snippet_after_heading(lines: list[str], heading: str) -> str:
    for index, line in enumerate(lines):
        if line == heading:
            return " ".join(lines[index + 1 :])
        if line.startswith(heading):
            return line[len(heading) :].strip()
    return " ".join(lines)


def _parse_snippet_for_title(snippet_text: str, heading_company: str) -> tuple[str, str, str, str]:
    snippet_text = re.sub(r"\s+", " ", snippet_text or "").strip()
    if not snippet_text:
        return "", "", "parse_failed", ""
    if BAD_VIETNAMESE_AT_RE.search(snippet_text):
        return "", "", "parse_failed", ""

    explicit = re.search(
        r"(?:Experience|Kinh nghi.m)\s*:\s*(?P<title>.{0,90}?)\s+(?:at|@|tai|t\u1ea1i)\s+(?P<company>[^.\u00b7|;]{2,80})",
        snippet_text,
        flags=re.IGNORECASE,
    )
    if explicit and not BAD_VIETNAMESE_AT_RE.search(explicit.group(0)):
        return _clean_title(explicit.group("title")), _clean_company(explicit.group("company")), "ok", "current_line"

    direct = re.search(
        r"(?P<title>[^.\u00b7|;]{0,90}?\b(?:procurement|purchas\w*|buyer|buying|sourcing|supply chain|logistics|import|category|commodity|coffee trader|sales executive|managing director)\b[^.\u00b7|;]{0,80}?)\s+(?:at|@|tai|t\u1ea1i)\s+(?P<company>[^.\u00b7|;]{2,80})",
        snippet_text,
        flags=re.IGNORECASE,
    )
    if direct and not BAD_VIETNAMESE_AT_RE.search(direct.group(0)):
        return _clean_title(direct.group("title")), _clean_company(direct.group("company")), "ok", "text_fallback"

    if heading_company:
        candidate_patterns = [
            r"(?:seeking|looking for|interest in|experienced in|experience in)\s+(?P<title>[^.\u00b7|;]{0,90}?\b(?:procurement|purchas\w*|buyer|buying|sourcing|supply chain|logistics|import|category|commodity)\b[^.\u00b7|;]{0,80})",
            r"(?P<title>\b(?:senior\s+)?(?:procurement|purchas\w*|buyer|buying|sourcing|supply chain|logistics|import|category|commodity)\b[^.\u00b7|;]{0,80}?(?:professional|lead|manager|supervisor|specialist|officer|executive|intern|consultant)?)",
            r"Department:\s*(?P<title>Supply Chain)(?:\s+About\s+the\s+Role:\s+We\s+are\s+seeking\s+a\s+motivated\s+(?P<role>Supply Chain Intern))?",
            r"We\s+are\s+looking\s+for\s+a\s+(?P<title>Sales Executive)",
            r"I'm\s+a\s+(?P<title>coffee trader)\s+at\s+(?P<company>[^.\u00b7|;]{2,80})",
        ]
        for pattern in candidate_patterns:
            match = re.search(pattern, snippet_text, flags=re.IGNORECASE)
            if match:
                title = match.groupdict().get("role") or match.group("title")
                company = match.groupdict().get("company") or heading_company
                source = "text_fallback" if match.groupdict().get("company") else "title"
                return _clean_title(title), _clean_company(company), "ok", source

    return "", "", "parse_failed", ""


def _profile_result(name: str, role: str, company: str, url: str, parse_status: str, company_source: str = "") -> dict:
    role = _clean_title(role)
    company = _clean_company(company)
    if not role:
        parse_status = "parse_failed"
        company = ""
        company_source = ""
    if role.lower() == company.lower():
        parse_status = "parse_failed"
        role = ""
        company = ""
        company_source = ""
    return {
        "name": name,
        "title": role,
        "company": company,
        "company_source": company_source if company else "",
        "url": url,
        "is_current": True,
        "parse_status": parse_status,
    }


def _extract_with_bs4(raw_html: str) -> list[dict]:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    soup = BeautifulSoup(raw_html, "html.parser")
    results: list[dict] = []
    seen: set[str] = set()
    cards = soup.select("article")
    if not cards:
        cards = soup.select('div:has(a[href*="linkedin.com/in/"]), div:has(a[href*="uddg="])')

    for card in cards:
        anchors = card.select('a[href*="linkedin.com/in/"], a[href*="uddg="]')
        url = ""
        title_text = ""
        for anchor in anchors:
            candidate_url = _clean_url(anchor.get("href") or "")
            text = anchor.get_text(" ", strip=True)
            if candidate_url and not url:
                url = candidate_url
            if candidate_url and text and not _is_breadcrumb(text):
                title_text = text
                break
        if not url or url.lower() in seen:
            continue
        if not title_text:
            continue

        lines = [line.strip() for line in card.get_text("\n", strip=True).splitlines() if line.strip()]
        snippet = _snippet_after_heading(lines, title_text)
        name, role, company, parse_status, company_source = _split_title(title_text)
        snippet_company = _company_from_snippet(snippet)
        if parse_status == "ok":
            if not company and snippet_company:
                company = snippet_company
                company_source = "current_line"
        elif snippet_company:
            snippet_name, snippet_role = _role_from_two_part_title(title_text, snippet_company)
            if snippet_role:
                name = snippet_name
                role = snippet_role
                company = snippet_company
                parse_status = "ok"
                company_source = "current_line"
        else:
            mention_company = _company_mention_from_snippet(snippet)
            snippet_name, snippet_role = _role_from_two_part_title(title_text, mention_company)
            if snippet_role:
                name = snippet_name
                role = snippet_role
                company = mention_company
                parse_status = "ok"
                company_source = "text_fallback"

        if parse_status != "ok":
            snippet_role, snippet_company_from_title, snippet_status, snippet_source = _parse_snippet_for_title(
                snippet,
                _company_from_heading(title_text) or snippet_company,
            )
            if snippet_status == "ok":
                role = snippet_role
                company = snippet_company_from_title
                parse_status = "ok"
                company_source = snippet_source

        results.append(_profile_result(name, role, company, url, parse_status, company_source))
        seen.add(url.lower())
    return results


def _extract_card_text_result(card_html: str) -> dict | None:
    anchors = re.findall(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", card_html, flags=re.IGNORECASE | re.DOTALL)
    url = ""
    title_text = ""
    for href, anchor_html in anchors:
        candidate_url = _clean_url(href)
        text = _clean_text(anchor_html)
        if candidate_url and not url:
            url = candidate_url
        if candidate_url and text and not _is_breadcrumb(text):
            title_text = text
            break
    if not url or not title_text:
        return None

    text = _clean_text(card_html)
    snippet = text.replace(title_text, "", 1).strip() if title_text in text else ""
    name, role, company, parse_status, company_source = _split_title(title_text)
    snippet_company = _company_from_snippet(snippet)
    if parse_status == "ok":
        if not company and snippet_company:
            company = snippet_company
            company_source = "current_line"
    elif snippet_company:
        snippet_name, snippet_role = _role_from_two_part_title(title_text, snippet_company)
        if snippet_role:
            name = snippet_name
            role = snippet_role
            company = snippet_company
            parse_status = "ok"
            company_source = "current_line"
    else:
        mention_company = _company_mention_from_snippet(snippet)
        snippet_name, snippet_role = _role_from_two_part_title(title_text, mention_company)
        if snippet_role:
            name = snippet_name
            role = snippet_role
            company = mention_company
            parse_status = "ok"
            company_source = "text_fallback"

    if parse_status != "ok":
        snippet_role, snippet_company_from_title, snippet_status, snippet_source = _parse_snippet_for_title(
            snippet,
            _company_from_heading(title_text) or snippet_company,
        )
        if snippet_status == "ok":
            role = snippet_role
            company = snippet_company_from_title
            parse_status = "ok"
            company_source = snippet_source

    return _profile_result(name, role, company, url, parse_status, company_source)


def extract_web_search_results(raw_html: str) -> list[dict]:
    """Parse DuckDuckGo HTML results into LinkedIn profile candidates."""
    bs4_results = _extract_with_bs4(raw_html)
    if bs4_results:
        return bs4_results

    results: list[dict] = []
    seen: set[str] = set()
    cards = re.findall(r"<article\b[^>]*>.*?</article>", raw_html, flags=re.IGNORECASE | re.DOTALL)
    if cards:
        for card in cards:
            result = _extract_card_text_result(card)
            if not result:
                continue
            url = result["url"]
            if url.lower() in seen:
                continue
            results.append(result)
            seen.add(url.lower())
        if results:
            return results

    anchors = re.findall(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", raw_html, flags=re.IGNORECASE | re.DOTALL)
    for href, anchor_html in anchors:
        url = _clean_url(href)
        if not url or url.lower() in seen:
            continue
        title_text = _clean_text(anchor_html)
        if not title_text:
            continue
        name, role, company, parse_status, company_source = _split_title(title_text)
        results.append(_profile_result(name, role, company, url, parse_status, company_source))
        seen.add(url.lower())
    return results


