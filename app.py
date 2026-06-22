"""FastAPI entrypoint for Lead Prospector Lite."""

import json
import math
import time
import unicodedata
import uuid
from pathlib import Path
from urllib.parse import quote_plus

from cachetools import TTLCache
from fastapi import Body, FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from engine import ddg_client
from engine.build_search_query import build_fallback_hyperlinks
from engine.dedup_profiles import dedup_profiles
from engine.extract_web_search_results import extract_web_search_results
from engine.score_profiles import score_profiles


BASE_DIR = Path(__file__).resolve().parent
APP_VERSION = "0.1.0"
CACHE_TTL_SECONDS = 24 * 60 * 60
COOKIE_MAX_AGE = 30 * 24 * 60 * 60


def _load_json(relative_path: str) -> dict:
    with (BASE_DIR / relative_path).open(encoding="utf-8") as file:
        return json.load(file)


SCORING_RULES = _load_json("config/scoring-rules.json")
TITLE_SYNONYMS = _load_json("config/title-synonyms.json")
ROLE_PRESETS = _load_json("config/role-presets.json")
SEARCH_CACHE: TTLCache = TTLCache(maxsize=512, ttl=CACHE_TTL_SECONDS)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limit_key(request: Request) -> str:
    uid = getattr(request.state, "uid", request.cookies.get("uid", "anonymous"))
    return f"{_client_ip(request)}:{uid}"


limiter = Limiter(key_func=_rate_limit_key)
app = FastAPI(title="Lead Prospector Lite", version=APP_VERSION)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


class SearchRequest(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    mst: str | None = None
    role: str

    @field_validator("company")
    @classmethod
    def validate_company(cls, value: str) -> str:
        company = value.strip()
        if not company:
            raise ValueError("Tên công ty không được để trống")
        return company

    @field_validator("mst")
    @classmethod
    def validate_mst(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        mst = value.strip()
        if not mst.isdigit() or len(mst) not in (10, 13):
            raise ValueError("MST phải gồm 10 hoặc 13 chữ số")
        return mst

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in ROLE_PRESETS:
            raise ValueError("Vai trò không hợp lệ")
        return value


@app.middleware("http")
async def ensure_uid_cookie(request: Request, call_next):
    existing_uid = request.cookies.get("uid")
    request.state.uid = existing_uid or str(uuid.uuid4())
    response = await call_next(request)
    if not existing_uid:
        response.set_cookie(
            "uid",
            request.state.uid,
            max_age=COOKIE_MAX_AGE,
            httponly=True,
            secure=True,
            samesite="lax",
        )
    return response


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(_: Request, __: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": "Hết lượt giờ này, quay lại sau 60 phút"},
    )


def _strip_accents(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    ).replace("Đ", "D").replace("đ", "d")


def _cache_key(company: str, role: str) -> tuple[str, str]:
    normalized = " ".join(company.casefold().split())
    return normalized, role


def _build_ddg_query(company: str, role: str) -> str:
    safe_company = " ".join(company.replace('"', " ").split())
    return f'site:linkedin.com/in "{safe_company}" {ROLE_PRESETS[role]}'


def _build_links(company: str, mst: str | None) -> dict[str, str]:
    fallback = build_fallback_hyperlinks(company, mst or "")
    return {
        "masothue": fallback["google_mst"],
        "google_website": fallback["google_website"],
        "google_company": "https://www.google.com/search?q=" + quote_plus(company),
    }


def _rate_limit_status(request: Request) -> dict[str, int]:
    current_limit = getattr(request.state, "view_rate_limit", None)
    if not current_limit:
        return {"remaining": 9, "reset_in_minutes": 60}
    reset_at, remaining = limiter.limiter.get_window_stats(
        current_limit[0], *current_limit[1]
    )
    reset_minutes = max(1, math.ceil((reset_at - time.time()) / 60))
    return {"remaining": remaining, "reset_in_minutes": reset_minutes}


def _public_profiles(profiles: list[dict]) -> list[dict]:
    return [
        {
            "name": profile.get("name", ""),
            "title": profile.get("title", ""),
            "company": profile.get("company", ""),
            "url": profile.get("url", ""),
            "score": profile.get("fit_score", 0),
        }
        for profile in profiles
    ]


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/status")
async def status() -> dict[str, object]:
    return {"ok": True, "version": APP_VERSION}


@app.post("/api/search")
@limiter.limit("10/hour")
async def search(request: Request, payload: SearchRequest = Body(...)):
    links = _build_links(payload.company, payload.mst)
    key = _cache_key(payload.company, payload.role)
    if key in SEARCH_CACHE:
        return {
            "profiles": SEARCH_CACHE[key],
            "links": links,
            "rate_limit": _rate_limit_status(request),
            "warnings": ["cached"],
        }

    query = _build_ddg_query(payload.company, payload.role)
    try:
        html = await run_in_threadpool(ddg_client.search, query)
        profiles = extract_web_search_results(html)
        if len(profiles) < 3 and _strip_accents(payload.company) != payload.company:
            accentless_query = _build_ddg_query(_strip_accents(payload.company), payload.role)
            second_html = await run_in_threadpool(ddg_client.search, accentless_query)
            profiles.extend(extract_web_search_results(second_html))
    except ddg_client.DDGBlocked:
        return JSONResponse(
            status_code=503,
            content={"error": "Hệ thống tạm nghỉ, thử lại sau 1 phút"},
        )
    except ddg_client.DDGEmpty:
        result: list[dict] = []
        SEARCH_CACHE[key] = result
        return {
            "profiles": result,
            "links": links,
            "rate_limit": _rate_limit_status(request),
            "warnings": ["Không tìm thấy profile nào"],
        }

    scored = score_profiles(
        profiles,
        payload.company,
        [],
        SCORING_RULES,
        TITLE_SYNONYMS,
        title_keywords=ROLE_PRESETS[payload.role],
    )
    ranked = sorted(dedup_profiles(scored), key=lambda item: item.get("fit_score", 0), reverse=True)
    result = _public_profiles(ranked[:3])
    SEARCH_CACHE[key] = result
    warnings = [] if result else ["Không tìm thấy profile nào"]
    return {
        "profiles": result,
        "links": links,
        "rate_limit": _rate_limit_status(request),
        "warnings": warnings,
    }
