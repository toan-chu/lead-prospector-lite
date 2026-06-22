from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote_plus


def _quote(value: str) -> str:
    escaped = value.strip().replace('"', '\\"')
    return f'"{escaped}"'


def _company_terms(company: str, company_variants: list[str]) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for value in [company, *company_variants]:
        cleaned = value.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            terms.append(cleaned)
    return terms


def _clean_expression(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def _has_vietnamese_diacritics(value: str) -> bool:
    return any(unicodedata.category(char) == "Mn" for char in unicodedata.normalize("NFD", value or ""))


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def slugify_company_name(value: str) -> str:
    normalized = _strip_accents(str(value or "").lower().replace("đ", "d"))
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    return normalized.strip("-")


def build_masothue_url(company_raw: str, mst: str = "") -> str:
    mst_clean = "".join(str(mst or "").split())
    if mst_clean and re.fullmatch(r"\d{10}|\d{13}", mst_clean):
        slug = slugify_company_name(company_raw)
        if slug:
            return f"https://masothue.com/{mst_clean}-{slug}"
        return "https://www.google.com/search?q=" + quote_plus(f'"{mst_clean}" masothue')
    return "https://www.google.com/search?q=" + quote_plus(f"{str(company_raw or '').strip()} ma so thue".strip())


def _strip_outer_parentheses(value: str) -> str:
    expression = _clean_expression(value)
    while expression.startswith("(") and expression.endswith(")"):
        depth = 0
        wraps = True
        for index, char in enumerate(expression):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0 and index != len(expression) - 1:
                    wraps = False
                    break
        if not wraps:
            break
        expression = expression[1:-1].strip()
    return expression


def _split_top_level_or(expression: str) -> list[str]:
    expression = _strip_outer_parentheses(expression)
    if not expression:
        return []
    parts: list[str] = []
    start = 0
    depth = 0
    in_quote = False
    for match in re.finditer(r'"|\(|\)|\bOR\b', expression, flags=re.IGNORECASE):
        token = match.group(0)
        if token == '"':
            in_quote = not in_quote
        elif not in_quote and token == "(":
            depth += 1
        elif not in_quote and token == ")":
            depth = max(depth - 1, 0)
        elif not in_quote and depth == 0 and token.upper() == "OR":
            parts.append(expression[start : match.start()].strip())
            start = match.end()
    parts.append(expression[start:].strip())
    return [part.strip().strip('"') for part in parts if part.strip()]


def build_web_search_queries(company: str, company_variants: list[str], title_keywords: str) -> list[str]:
    title_terms = _split_top_level_or(title_keywords) or [_clean_expression(title_keywords)]
    company_terms = [company]
    if _has_vietnamese_diacritics(company):
        company_terms.append(_strip_accents(company))
    queries: list[str] = []
    seen: set[str] = set()
    for company_term in _company_terms(company_terms[0], [*company_terms[1:], *company_variants]):
        for term in title_terms:
            if not term:
                continue
            query = f"site:linkedin.com/in {_quote(company_term)} {term}"
            key = query.lower()
            if key not in seen:
                seen.add(key)
                queries.append(query)
    return queries


def build_web_search_query(company: str, company_variants: list[str], title_keywords: str) -> str:
    queries = build_web_search_queries(company, company_variants, title_keywords)
    return queries[0] if queries else f"site:linkedin.com/in {_quote(company)}"



def build_fallback_hyperlinks(company_raw: str, mst: str = "") -> dict[str, str]:
    """Build fallback URLs from the original raw company name.

    Google MST and website searches benefit from the full legal name for
    disambiguation. LinkedIn runtime queries are built separately from cleaned
    company names.
    """
    cleaned = str(company_raw or "").strip()
    return {
        "linkedin_search": "https://www.linkedin.com/search/results/people/?keywords=" + quote_plus(f"{cleaned} procurement".strip()),
        "ddg_search": "https://duckduckgo.com/?q=" + quote_plus(f'site:linkedin.com/in "{cleaned}" procurement'.strip()),
        "google_mst": build_masothue_url(cleaned, mst),
        "google_website": "https://www.google.com/search?q=" + quote_plus(f"{cleaned} official website".strip()),
    }


