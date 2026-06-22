from __future__ import annotations

import re
import unicodedata
from typing import Any


def _norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def _normalize_company_name(name: str) -> str:
    if not name:
        return ""
    text = _norm(name)
    text = re.sub(r"[+.,()\[\]]", " ", text)
    text = re.sub(r"\bviet\s+nam\b", "vietnam", text)
    text = re.sub(r"\s+", " ", text).strip()
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\b([a-z])\s+([a-z])\b", r"\1\2", text)
    return text


_LEGAL_SUFFIX_WORDS = {
    "jsc",
    "ltd",
    "limited",
    "co",
    "corp",
    "corporation",
    "company",
    "inc",
    "group",
    "holdings",
    "vietnam",
    "vn",
    "joint",
    "stock",
    "cong",
    "ty",
    "co",
    "phan",
    "tnhh",
    "trach",
    "nhiem",
    "huu",
    "han",
    # Industry descriptor words thÆ°á»ng gáº·p trong tÃªn phÃ¡p lÃ½ VN (vd "CÃ´ng ty CP chÄƒn nuÃ´i C.P. Viá»‡t Nam").
    # Trade-off cÃ³ chá»§ Ä‘Ã­ch: cho phÃ©p match tÃªn rÃºt gá»n vs tÃªn Ä‘Äƒng kÃ½ Ä‘áº§y Ä‘á»§,
    # Ä‘á»•i láº¡i "X ChÄƒn NuÃ´i" (subsidiary) sáº½ match input "X". Review láº¡i á»Ÿ Round 6 (MST resolver).
    "chan",
    "nuoi",
}


def _company_from_title(title: str) -> str:
    at_match = re.search(r"\bat\s+(.+)$", title, flags=re.IGNORECASE)
    if not at_match:
        return ""
    company = re.split(r"\s+-\s+|,", at_match.group(1), maxsplit=1)[0]
    return company.strip(" .,-")


def _terms_from_keywords(keywords: str) -> tuple[list[str], list[str]]:
    has_operator = bool(re.search(r"\b(AND|OR|NOT)\b|[()]", keywords, flags=re.IGNORECASE))
    quoted = [term.strip().lower() for term in re.findall(r'"([^"]+)"', keywords) if term.strip()]
    cleaned = re.sub(r"\b(AND|OR|NOT)\b|[()\"]", " ", keywords, flags=re.IGNORECASE)
    words = [term.lower() for term in re.findall(r"[A-Za-z0-9+#]+", cleaned) if term.strip()]
    if not has_operator and len(words) > 1:
        exact_terms = quoted + [" ".join(words)]
    else:
        exact_terms = quoted + words
    return exact_terms, words


def _keyword_mode(keywords: str) -> str:
    if re.search(r"\bAND\b", keywords, flags=re.IGNORECASE) and not re.search(r"\bOR\b", keywords, flags=re.IGNORECASE):
        return "all"
    return "any"


def _has_boolean_syntax(keywords: str) -> bool:
    return bool(re.search(r"\b(AND|OR|NOT)\b|[()\"]", keywords, flags=re.IGNORECASE))


def _contains(text: str, term: str) -> bool:
    return term and term.lower() in text


def _matches_whole_word_title(title: str, pattern: str) -> bool:
    raw = str(pattern or "").strip()
    if not raw:
        return False
    return bool(re.search(rf"\b{re.escape(raw)}\b", title, flags=re.IGNORECASE))


def _matches_terms(text: str, terms: list[str], mode: str) -> bool:
    meaningful = [term for term in terms if term]
    if not meaningful:
        return False
    if mode == "all":
        return all(_contains(text, term) for term in meaningful)
    return any(_contains(text, term) for term in meaningful)


def _matches_synonyms(text: str, terms: list[str], synonyms: dict[str, set[str]], mode: str) -> bool:
    meaningful = [term for term in terms if term]
    if not meaningful:
        return False

    def matches_one(term: str) -> bool:
        term_norm = _norm(term)
        return _contains(text, term_norm) or any(_contains(text, synonym) for synonym in synonyms.get(term_norm, set()))

    if mode == "all":
        return all(matches_one(term) for term in meaningful)
    return any(matches_one(term) for term in meaningful)


def _boolean_tokens(expression: str) -> list[str]:
    pattern = re.compile(r'"[^"]*"|\(|\)|\bAND\b|\bOR\b|\bNOT\b|[^\s()]+', re.IGNORECASE)
    return [match.group(0) for match in pattern.finditer(expression or "")]


def _term_matches(text: str, term: str, synonyms: dict[str, set[str]]) -> bool:
    cleaned = term.strip().strip('"')
    if not cleaned:
        return False
    normalized = _norm(cleaned)
    return _contains(text, normalized) or any(_contains(text, synonym) for synonym in synonyms.get(normalized, set()))


class _BooleanMatcher:
    def __init__(self, expression: str, text: str, synonyms: dict[str, set[str]]) -> None:
        self.tokens = _boolean_tokens(expression)
        self.text = text
        self.synonyms = synonyms
        self.index = 0

    def match(self) -> bool:
        if not self.tokens:
            return False
        result = self._parse_or()
        return result

    def _peek(self) -> str | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def _take(self) -> str | None:
        token = self._peek()
        if token is not None:
            self.index += 1
        return token

    def _parse_or(self) -> bool:
        result = self._parse_and()
        while (self._peek() or "").upper() == "OR":
            self._take()
            right = self._parse_and()
            result = result or right
        return result

    def _parse_and(self) -> bool:
        result = self._parse_not()
        while (self._peek() or "").upper() == "AND":
            self._take()
            right = self._parse_not()
            result = result and right
        return result

    def _parse_not(self) -> bool:
        if (self._peek() or "").upper() == "NOT":
            self._take()
            return not self._parse_not()
        return self._parse_primary()

    def _parse_primary(self) -> bool:
        token = self._take()
        if token is None:
            return False
        if token == "(":
            result = self._parse_or()
            if self._peek() == ")":
                self._take()
            return result
        if token == ")":
            return False
        return _term_matches(self.text, token, self.synonyms)


def _matches_boolean_expression(text: str, expression: str, synonyms: dict[str, set[str]]) -> bool:
    expression = (expression or "").strip()
    if not expression:
        return False
    if not _has_boolean_syntax(expression):
        return _term_matches(text, expression, synonyms)
    return _BooleanMatcher(expression, text, synonyms).match()


def _company_match_confidence(profile_company: str, company: str, variants: list[str]) -> str:
    """Return 'exact', 'strong', 'short_variant', or '' for no acceptable company match.

    'short_variant': match achieved ONLY via a short variant (<=4 chars after normalize).
    Short abbreviations (e.g. "DCM") collide globally - they may confirm but must not
    establish identity, so the output layer downgrades these leads to NEEDS_REVIEW.
    The primary input company name (index 0) is always trusted at full confidence.
    """
    primary = re.split(r"\s+-\s+|\s+such as\s+|\s+including\s+|\s+clients?:|,", str(profile_company or ""), maxsplit=1, flags=re.IGNORECASE)[0]
    profile = _normalize_company_name(primary)
    if not profile:
        return ""
    best = ""
    for index, candidate in enumerate([company, *variants]):
        cur = _normalize_company_name(candidate)
        if not cur:
            continue
        level = ""
        if profile == cur:
            level = "exact"
        elif len(profile) > 4:
            boundary = rf"(?<![a-z0-9]){re.escape(cur)}(?![a-z0-9])"
            if re.search(boundary, profile):
                remainder = [word for word in re.sub(boundary, " ", profile).split() if word]
                if all(word in _LEGAL_SUFFIX_WORDS for word in remainder):
                    level = "strong"
            if not level:
                reverse_boundary = rf"(?<![a-z0-9]){re.escape(profile)}(?![a-z0-9])"
                if re.search(reverse_boundary, cur):
                    remainder = [word for word in re.sub(reverse_boundary, " ", cur).split() if word]
                    if all(word in _LEGAL_SUFFIX_WORDS for word in remainder):
                        level = "strong"
        if not level:
            continue
        if index > 0 and len(cur) <= 4:
            if best == "":
                best = "short_variant"
            continue
        if level == "exact":
            return "exact"
        if best in ("", "short_variant"):
            best = "strong"
    return best


def _company_matches(profile_company: str, company: str, variants: list[str]) -> bool:
    return _company_match_confidence(profile_company, company, variants) != ""


def _compact_company(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _normalize_company_name(value))


def _v1_generic_words(policy: dict) -> set[str]:
    return {_normalize_company_name(word) for word in policy.get("generic_company_words", []) if _normalize_company_name(word)}


def _company_match_confidence_v1(profile_company: str, company: str, variants: list[str], policy: dict, *, mention: bool = False) -> str:
    profile = _normalize_company_name(profile_company)
    if not profile:
        return ""
    generic_words = _v1_generic_words(policy) or _LEGAL_SUFFIX_WORDS
    best = ""
    for index, candidate in enumerate([company, *variants]):
        cur = _normalize_company_name(candidate)
        if not cur:
            continue
        level = ""
        if profile == cur or _compact_company(profile) == _compact_company(cur):
            level = "exact"
        else:
            boundary = rf"(?<![a-z0-9]){re.escape(cur)}(?![a-z0-9])"
            reverse_boundary = rf"(?<![a-z0-9]){re.escape(profile)}(?![a-z0-9])"
            if re.search(boundary, profile):
                remainder = [word for word in re.sub(boundary, " ", profile).split() if word]
                level = "strong" if all(word in generic_words for word in remainder) else "partial"
            elif re.search(reverse_boundary, cur):
                remainder = [word for word in re.sub(reverse_boundary, " ", cur).split() if word]
                level = "strong" if all(word in generic_words for word in remainder) else "partial"
            elif _compact_company(cur) and _compact_company(cur) in _compact_company(profile):
                level = "partial"
        if not level:
            continue
        if mention:
            level = "mention"
        elif index > 0 and len(cur) <= 4:
            level = "short_variant"
        order = {"": 0, "mention": 1, "short_variant": 2, "partial": 3, "strong": 4, "exact": 5}
        if order[level] > order.get(best, 0):
            best = level
    return best


def _confidence_rank(value: str) -> int:
    return {"": 0, "mention": 1, "short_variant": 2, "partial": 3, "strong": 4, "exact": 5}.get(value, 0)


def _v1_best_company_match(profile: dict, company: str, variants: list[str], policy: dict) -> tuple[str, str]:
    fields = [
        ("title", profile.get("company") or ""),
        ("experience", profile.get("experience_company") or ""),
    ]
    best_confidence = ""
    best_source = ""
    for source, value in fields:
        confidence = _company_match_confidence_v1(str(value), company, variants, policy)
        if _confidence_rank(confidence) > _confidence_rank(best_confidence):
            best_confidence = confidence
            best_source = source
    if _confidence_rank(best_confidence) >= _confidence_rank("strong"):
        return best_confidence, best_source
    mention_text = " ".join(str(profile.get(key) or "") for key in ("headline_raw", "snippet", "title"))
    mention_confidence = _company_match_confidence_v1(mention_text, company, variants, policy, mention=True)
    if _confidence_rank(mention_confidence) > _confidence_rank(best_confidence):
        return mention_confidence, "mention"
    return best_confidence, best_source


def _contains_any_norm(text: str, terms: list[str]) -> bool:
    haystack = _norm(text)
    return any(_norm(term) and _norm(term) in haystack for term in terms)


def _location_is_vietnam(location: str) -> bool | None:
    norm = _norm(location)
    if not norm:
        return None
    vietnam_markers = ["vietnam", "viet nam", "ho chi minh", "hanoi", "ha noi", "phu my", "district", "ba ria", "vung tau"]
    if any(marker in norm for marker in vietnam_markers):
        return True
    foreign_markers = ["belgium", "australia", "united states", "usa", "singapore", "netherlands"]
    if any(marker in norm for marker in foreign_markers):
        return False
    return None


def _quality_score(profile: dict) -> int:
    quality = 0
    if profile.get("has_summary"):
        quality += 1
    if profile.get("education"):
        quality += 1
    if int(profile.get("connections") or 0) >= 50:
        quality += 1
    if profile.get("title"):
        quality += 1
    elif profile.get("company") or profile.get("experience_company"):
        quality += 1
    if profile.get("is_current") is not None:
        quality += 1
    return quality


def _weighted_score(profile: dict, confidence: str, context: str, policy: dict) -> int:
    base = {"exact": 10, "strong": 8, "partial": 4, "short_variant": 3, "mention": 1}.get(confidence, 0)
    weights = policy.get("weights", {})
    score = base
    location_state = _location_is_vietnam(str(profile.get("location") or ""))
    if location_state is True:
        score += int(weights.get("location_vn", 0))
    elif location_state is False:
        score += int(weights.get("location_foreign", 0))
    if context and _contains_any_norm(" ".join(str(profile.get(key) or "") for key in ("title", "headline_raw", "location")), [context]):
        score += int(weights.get("context_match", 0))
    if profile.get("has_summary"):
        score += int(weights.get("has_summary", 0))
    if profile.get("education"):
        score += int(weights.get("has_education", 0))
    if int(profile.get("connections") or 0) >= 50:
        score += int(weights.get("connections_50plus", 0))
    if confidence == "short_variant":
        score += int(weights.get("short_variant_penalty", 0))
    if confidence == "mention":
        score += int(weights.get("mention_only_penalty", 0))
    if profile.get("is_current") is False:
        score += int(weights.get("past_position", 0))
    else:
        score += int(weights.get("current_position", 0))
    return score


def _v1_tier(profile: dict, confidence: str, weighted_score: int, policy: dict) -> str:
    if not confidence:
        return ""
    if weighted_score < int(policy.get("tier_thresholds", {}).get("needs_review_min", 0)):
        return ""
    is_current = profile.get("is_current")
    if is_current is False and _confidence_rank(confidence) >= _confidence_rank("strong"):
        return "D"
    if _confidence_rank(confidence) >= _confidence_rank("strong"):
        if _contains_any_norm(str(profile.get("title") or ""), policy.get("tier_a_roles", [])):
            return "A"
        return "B"
    return "C"


def score_lead_decisions(profiles: list[dict], company: str, company_variants: list[str], policy: dict, context: str = "") -> list[dict]:
    """Score profiles using V1 human-logic tiering without changing legacy scoring."""
    decisions: list[dict] = []
    blacklist = policy.get("blacklist_titles", [])
    for profile in profiles:
        enriched = dict(profile)
        enriched.setdefault("input_company", company)
        enriched["tier"] = ""
        enriched["quality"] = _quality_score(profile)
        enriched["weighted_score"] = 0
        enriched["score_decision"] = "rejected"
        enriched["lead_status"] = ""
        enriched["reject_reason"] = None
        if str(profile.get("parse_status") or "ok") != "ok":
            enriched["reject_reason"] = "parse_failed"
            decisions.append(enriched)
            continue
        if _contains_any_norm(str(profile.get("title") or ""), blacklist):
            enriched["reject_reason"] = "blacklist_title"
            decisions.append(enriched)
            continue
        confidence, source = _v1_best_company_match(profile, company, company_variants, policy)
        enriched["company_match_confidence"] = confidence
        enriched["company_source"] = source
        weighted = _weighted_score(profile, confidence, context, policy)
        enriched["weighted_score"] = weighted
        tier = _v1_tier(profile, confidence, weighted, policy)
        enriched["tier"] = tier
        if not tier:
            enriched["reject_reason"] = "company_no_match" if not confidence else "below_min_score"
            decisions.append(enriched)
            continue
        enriched["score_decision"] = "retained"
        enriched["fit_score"] = weighted
        enriched["match_type"] = confidence
        enriched["lead_status"] = "NEEDS_REVIEW" if tier == "C" else ("PAST_THREAD" if tier == "D" else "has_lead")
        decisions.append(enriched)
    return decisions


def _synonym_map(title_synonyms: dict) -> dict[str, set[str]]:
    raw = title_synonyms.get("synonyms", title_synonyms)
    expanded: dict[str, set[str]] = {}
    for root, values in raw.items():
        group = {_norm(root), *{_norm(value) for value in values}}
        for term in group:
            expanded.setdefault(term, set()).update(group - {term})
    return expanded


def score_profile_decisions(
    profiles: list[dict],
    company: str,
    company_variants: list[str],
    scoring_rules: dict,
    title_synonyms: dict,
    keywords: str = "",
    title_keywords: str = "",
    level_keywords: str = "",
) -> list[dict]:
    """Return every profile with its scoring decision and reject reason."""
    weights = scoring_rules.get("weights", {})
    min_score = scoring_rules.get("min_score_to_include", 50)
    include_past = scoring_rules.get("position_filter", {}).get("include_past", False)
    excluded_titles = scoring_rules.get("exclude_titles_whole_word") or scoring_rules.get("exclude_titles", [])
    title_expression = title_keywords or keywords
    del level_keywords
    exact_terms, partial_terms = _terms_from_keywords(title_expression)
    keyword_mode = _keyword_mode(title_expression)
    synonyms = _synonym_map(title_synonyms)

    decisions: list[dict] = []
    for profile in profiles:
        enriched = dict(profile)
        enriched["fit_score"] = 0
        enriched["match_type"] = ""
        enriched["input_company"] = company
        enriched["score_decision"] = "rejected"
        enriched["reject_reason"] = None
        enriched["company_match_confidence"] = ""

        parse_status = str(profile.get("parse_status") or "ok")
        profile_title_raw = str(profile.get("title") or "").strip()
        profile_company_raw = str(profile.get("company") or "").strip()
        raw_company_source = str(profile.get("company_source") or "").strip()
        if raw_company_source:
            company_source = raw_company_source
        elif profile.get("_source") or profile.get("score_decision"):
            company_source = "text_fallback"
        else:
            company_source = "title"
        enriched["company_source"] = company_source

        if parse_status != "ok":
            enriched["reject_reason"] = "parse_failed"
            decisions.append(enriched)
            continue
        if not profile_title_raw:
            enriched["reject_reason"] = "missing_title"
            decisions.append(enriched)
            continue
        if not profile_company_raw:
            enriched["reject_reason"] = "missing_company"
            decisions.append(enriched)
            continue
        if not include_past and profile.get("is_current", True) is False:
            enriched["reject_reason"] = "past_position"
            decisions.append(enriched)
            continue

        for excluded in excluded_titles:
            if _matches_whole_word_title(profile_title_raw, str(excluded)):
                enriched["reject_reason"] = f"excluded_title:{excluded}"
                decisions.append(enriched)
                break
        if enriched["reject_reason"]:
            continue

        title_employer = _company_from_title(profile_title_raw)
        if title_employer and not _company_matches(title_employer, company, company_variants):
            enriched["reject_reason"] = f"title_employer_mismatch:{title_employer[:40]}"
            decisions.append(enriched)
            continue

        title = _norm(profile_title_raw)
        confidence = "" if company_source == "text_fallback" else _company_match_confidence(profile_company_raw, company, company_variants)
        enriched["company_match_confidence"] = confidence
        company_matched = bool(confidence)
        score = 0
        match_type = ""
        if _has_boolean_syntax(title_expression) and _matches_boolean_expression(title, title_expression, {}):
            score = weights.get("company_match_AND_exact_title" if company_matched else "no_company_match_AND_exact_title", 100 if company_matched else 30)
            match_type = "exact"
        elif _matches_terms(title, exact_terms, keyword_mode):
            score = weights.get("company_match_AND_exact_title" if company_matched else "no_company_match_AND_exact_title", 100 if company_matched else 30)
            match_type = "exact"
        elif _has_boolean_syntax(title_expression) and _matches_boolean_expression(title, title_expression, synonyms):
            score = weights.get("company_match_AND_synonym_title" if company_matched else "no_company_match_AND_synonym_title", 90 if company_matched else 20)
            match_type = "synonym"
        elif _matches_synonyms(title, exact_terms, synonyms, keyword_mode):
            score = weights.get("company_match_AND_synonym_title" if company_matched else "no_company_match_AND_synonym_title", 90 if company_matched else 20)
            match_type = "synonym"
        elif _matches_terms(title, partial_terms, keyword_mode):
            score = weights.get("company_match_AND_partial_title", 60) if company_matched else weights.get("no_match", 0)
            match_type = "partial"

        enriched["fit_score"] = score
        enriched["match_type"] = match_type
        if score >= min_score:
            enriched["score_decision"] = "retained"
            enriched["reject_reason"] = None
        else:
            enriched["reject_reason"] = "company_mention_only" if company_source == "text_fallback" and _company_match_confidence(profile_company_raw, company, company_variants) else "below_min_score"
        decisions.append(enriched)
    return decisions


def score_profiles(
    profiles: list[dict],
    company: str,
    company_variants: list[str],
    scoring_rules: dict,
    title_synonyms: dict,
    keywords: str = "",
    title_keywords: str = "",
    level_keywords: str = "",
) -> list[dict]:
    """Apply deterministic title/company scoring and return included profiles."""
    return [
        profile
        for profile in score_profile_decisions(
            profiles,
            company,
            company_variants,
            scoring_rules,
            title_synonyms,
            keywords,
            title_keywords,
            level_keywords,
        )
        if profile.get("score_decision") == "retained"
    ]


