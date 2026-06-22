# Lead Prospector Lite — Blueprint

**Audience:** Codex (executor). Read fully before generating any code. Do not invent fields not listed here.

**Origin:** Fork snapshot từ `control-tower/skills/lead-prospector/` tại 2026-06-22. Sau khi build xong là độc lập, không sync auto với control-tower.

---

## 1. Mục tiêu sản phẩm

Web app demo MVP cho non-tech user. Input 1 công ty → output 3 LinkedIn profile relevant nhất + 3 link bổ sung (masothue, Google website, Google company name).

**Persona:** Sales/BD nhỏ lẻ, không biết Boolean search, dùng trên điện thoại/laptop, click URL là xong.

**Phạm vi rõ:**
- KHÔNG mass search (single company per request).
- KHÔNG login.
- KHÔNG lưu lịch sử search per-user (chỉ cache server-side 24h).
- KHÔNG Excel input/output (chỉ form web + CSV download).

---

## 2. Stack & Deploy

| Layer | Choice | Lý do |
|---|---|---|
| Backend | FastAPI 0.115+ | Async, simple, port Python code từ control-tower được |
| Rate limit | `slowapi` 0.1.9+ | FastAPI port của Flask-Limiter |
| Cache | `cachetools` TTLCache in-memory | TTL 24h, mất khi container restart (OK) |
| HTML parse | `beautifulsoup4` + `lxml` | Giống control-tower |
| Templates | Jinja2 (có sẵn trong FastAPI) | Render `index.html` |
| Frontend | Vanilla HTML + CSS + JS (1 file) | Không React, không build step |
| Container | Docker (HF Spaces Docker SDK) | Native HF |
| Host | Hugging Face Spaces (Free CPU basic) | Free, không cold start, public URL |
| CI/CD | GitHub Action `huggingface/[email protected]` | Push GitHub → auto mirror HF |

**KHÔNG dùng Playwright** trong MVP. Chỉ urllib hit `https://html.duckduckgo.com/html/`.

---

## 3. Folder structure (cuối cùng)

```
lead-prospector-lite/
├── .github/
│   └── workflows/
│       └── sync-to-hf.yml          # GitHub Action push code sang HF Space
├── docs/
│   ├── BLUEPRINT.md                # file này
│   ├── SOURCE_REFERENCE.md         # đường dẫn file gốc trong control-tower
│   └── DEPLOY.md                   # hướng dẫn deploy step-by-step
├── engine/
│   ├── __init__.py
│   ├── build_search_query.py       # PORT từ control-tower
│   ├── extract_web_search_results.py  # PORT
│   ├── score_profiles.py           # PORT (tune threshold + exclude list)
│   ├── dedup_profiles.py           # PORT (bỏ phần knowledge file scan)
│   ├── url_utils.py                # PORT từ shared/tools/
│   ├── validate_boolean.py         # PORT
│   └── ddg_client.py               # NEW — urllib + UA rotation + delay
├── config/
│   ├── scoring-rules.json          # PORT, raise min_score 50→70, exclude mở rộng
│   ├── title-synonyms.json         # PORT nguyên
│   └── role-presets.json           # NEW — map dropdown role → Boolean
├── static/
│   ├── style.css                   # Google-style + Arcane neon + Nyan animation
│   └── nyan.png                    # 8bit sprite Nyan Cat (1 PNG, ~5KB)
├── templates/
│   └── index.html                  # 1 page, vanilla JS
├── app.py                          # FastAPI entrypoint
├── requirements.txt
├── Dockerfile
├── .gitignore
├── .dockerignore
├── README.md                       # public-facing intro + deploy badge
└── LICENSE                         # MIT (default cho HF public)
```

---

## 4. Contract từng file

### 4.1 `engine/build_search_query.py`
- **Port nguyên** từ `control-tower/skills/lead-prospector/engine/build_search_query.py`.
- Giữ functions: `build_web_search_queries`, `build_web_search_query`, `build_masothue_url`, `build_fallback_hyperlinks`, `slugify_company_name`, `_quote`.
- **Bỏ:** `build_linkedin_query`, `build_linkedin_search_queries`, `build_fanout_queries` (không dùng — lite chỉ DDG search).

### 4.2 `engine/extract_web_search_results.py`
- **Port nguyên 100%** (365 LOC). Không tune. Logic parse DDG HTML này đã qua nhiều round.
- Phụ thuộc: `shared.tools.url_utils` → đổi import thành `from engine.url_utils import normalize_linkedin_profile_url`.

### 4.3 `engine/score_profiles.py`
- **Port nguyên** (583 LOC).
- Phụ thuộc: load `config/scoring-rules.json` + `config/title-synonyms.json`.
- Hàm dùng từ app: `score_profiles(profiles, company, title_keywords, level_keywords=None, config=...)`.

### 4.4 `engine/dedup_profiles.py`
- **Đơn giản hóa**: bỏ phần `_seen_urls(knowledge_path)` (lite không có knowledge file).
- Giữ logic: dedup trong batch theo URL chuẩn hóa.
- Signature mới: `def dedup_profiles(profiles: list[dict]) -> list[dict]`.

### 4.5 `engine/url_utils.py`
- **Port nguyên** từ `control-tower/shared/tools/url_utils.py`.
- Function chính: `normalize_linkedin_profile_url(url, with_scheme=False)`.

### 4.6 `engine/validate_boolean.py`
- **Port nguyên** (59 LOC).
- Dùng để validate khi user mở Advanced text field.

### 4.7 `engine/ddg_client.py` (NEW — ~80 LOC)
```python
"""DuckDuckGo search client — urllib only, no Playwright."""
import random
import time
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from urllib.error import URLError

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

BLOCK_MARKERS = [
    "anomaly detected", "bots use duckduckgo too", "rate limit",
    "too many requests", "challenge-form", "captcha",
]

class DDGBlocked(RuntimeError):
    pass

class DDGEmpty(RuntimeError):
    pass

def search(query: str, timeout: int = 30, min_delay: float = 2.0, max_delay: float = 4.0) -> str:
    """Hit html.duckduckgo.com/html/ with rotating UA + random delay. Returns HTML."""
    time.sleep(random.uniform(min_delay, max_delay))
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    req = Request(url, headers={
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
    })
    try:
        html = urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
    except URLError as exc:
        raise DDGBlocked(f"Network error: {exc}") from exc
    lower = html.lower()
    if any(marker in lower for marker in BLOCK_MARKERS):
        raise DDGBlocked("DuckDuckGo block/challenge page detected")
    if "no results" in lower or 'data-testid="no-results"' in html:
        raise DDGEmpty("No results from DuckDuckGo")
    return html
```

### 4.8 `config/scoring-rules.json`
```json
{
  "weights": {
    "company_match_AND_exact_title": 100,
    "company_match_AND_synonym_title": 90,
    "company_match_AND_partial_title": 70,
    "no_company_match_AND_exact_title": 30,
    "no_company_match_AND_synonym_title": 20,
    "no_match": 0
  },
  "position_filter": { "include_current": true, "include_past": false },
  "min_score_to_include": 70,
  "require_fields": { "title_present": true, "company_present": true, "headline_intact": true },
  "exclude_titles_whole_word": [
    "Intern", "Trainee", "HR Manager", "Marketing Manager", "IT Manager",
    "Finance Manager", "Accountant", "Receptionist", "Founder", "CEO", "Chairman"
  ],
  "exclude_match_mode": "whole_word"
}
```
**Diff so với gốc:** raise `min_score_to_include` 50→70; thêm `Founder`, `CEO`, `Chairman`; raise `partial_title` 60→70.

### 4.9 `config/title-synonyms.json`
- **Port nguyên** từ control-tower.

### 4.10 `config/role-presets.json` (NEW)
```json
{
  "procurement": "(Procurement OR Purchasing OR Buyer OR Sourcing OR \"Vendor Management\")",
  "sales": "(Sales OR \"Business Development\" OR \"Account Manager\" OR Commercial)",
  "logistics": "(Logistics OR Shipping OR Forwarding OR \"Import Export\" OR Freight)",
  "supply_chain": "(\"Supply Chain\" OR SCM OR Operations OR Planning OR Warehouse)"
}
```

### 4.11 `app.py` (FastAPI entrypoint, ~120 LOC)

**Endpoints:**
- `GET /` → render `index.html`.
- `POST /api/search` → JSON body `{company: str, mst: str|None, role: str}` → returns:
  ```json
  {
    "profiles": [
      {"name": "...", "title": "...", "company": "...", "url": "...", "score": 90}
    ],
    "links": {
      "masothue": "https://masothue.com/...",
      "google_website": "https://www.google.com/search?q=...",
      "google_company": "https://www.google.com/search?q=..."
    },
    "rate_limit": {"remaining": 7, "reset_in_minutes": 42},
    "warnings": []
  }
  ```
- `GET /api/status` → `{"ok": true, "version": "0.1.0"}` (health check cho HF).

**Logic `/api/search`:**
1. Apply slowapi limit `10/hour` keyed by `f"{ip}:{cookie_uid}"`.
2. Check cache `(company_normalized, role)` → hit thì return cache + warning="cached".
3. Build query: `site:linkedin.com/in "{company}" {role_boolean}`.
4. Call `ddg_client.search(query)` → HTML.
5. `extract_web_search_results(html)` → list profile.
6. Nếu `len(profiles) < 3` và company có dấu tiếng Việt → build query variant không dấu, hit DDG lần 2, merge.
7. `score_profiles(...)` → score + filter ≥70.
8. `dedup_profiles(...)` → dedup URL.
9. Sort theo score desc, lấy top 3.
10. Build `links` từ `build_fallback_hyperlinks(company, mst)`.
11. Cache result 24h.
12. Return JSON.

**Error handling:**
- `DDGBlocked` → return 503 + `{"error": "Hệ thống tạm nghỉ, thử lại sau 1 phút"}`.
- `DDGEmpty` → return 200 + `{"profiles": [], "links": {...}, "warnings": ["Không tìm thấy profile nào"]}`.
- Slowapi rate exceeded → return 429 + `{"error": "Hết lượt giờ này, quay lại sau X phút"}`.

**Cookie:** set `uid` HttpOnly Secure SameSite=Lax, expires 30 ngày, value = `uuid.uuid4()` nếu chưa có.

**X-Forwarded-For:** HF Spaces có reverse proxy → đọc header `x-forwarded-for` để lấy IP thật (lấy giá trị đầu tiên trước dấu phẩy).

### 4.12 `templates/index.html` (Google-style + Nyan + Arcane)

**Layout:**
- Background: gradient diagonal `#1a0533 → #4a1c5e → #ff1493 → #00d4ff` với noise texture overlay (CSS `radial-gradient` + `filter: blur`).
- Header (top 80px): Nyan Cat sprite chạy ngang từ phải sang trái, loop infinite, để lại trail cầu vồng (CSS `@keyframes`).
- Main center: card max-width 600px, glassmorphism (`backdrop-filter: blur(20px)` + `background: rgba(255,255,255,0.05)` + neon border `1px solid rgba(255,20,147,0.5)`).
- Logo: text "Lead Prospector Lite" font Orbitron hoặc Press Start 2P (Google Fonts), gradient text fill, glow shadow.
- Subtitle: "Tìm 3 PIC LinkedIn relevant cho công ty bạn"
- Form:
  - Input 1: "Tên công ty" (required, autofocus)
  - Input 2: "MST (optional)" — chỉ nhận 10 hoặc 13 số, validate client-side
  - Select 3: dropdown role — Procurement / Sales / Logistics / Supply Chain
  - Button "Tìm" — neon pink, hover glow
- Counter chip top-right: "Còn 8/10 lượt giờ này" (cập nhật sau mỗi search).
- Results section (hidden ban đầu):
  - 3 profile card horizontal: avatar placeholder + name + title + company + score badge + button "Mở LinkedIn".
  - Section "Liên kết bổ sung": 3 chip link MST + Google Website + Google Company.
  - Button "Download CSV" (top-right results).
- Loading state: Nyan Cat chạy nhanh hơn + spinner trên button.
- Error state: banner đỏ neon ở giữa với message từ backend.

**JavaScript (vanilla, ~100 LOC):**
- Form submit → fetch `/api/search` POST → render results.
- CSV download: build blob client-side từ array results.
- Rate limit counter persist trong sessionStorage (chỉ visual, backend là ground truth).

### 4.13 `static/style.css`

**Arcane palette:**
```css
:root {
  --arcane-violet: #4a1c5e;
  --arcane-pink: #ff1493;
  --arcane-cyan: #00d4ff;
  --arcane-dark: #0a0118;
  --neon-glow: 0 0 20px rgba(255, 20, 147, 0.6), 0 0 40px rgba(0, 212, 255, 0.3);
}
```

**Nyan animation:**
```css
@keyframes nyan-fly {
  0% { transform: translateX(110vw); }
  100% { transform: translateX(-200px); }
}
.nyan {
  position: fixed; top: 20px; height: 60px; width: auto;
  animation: nyan-fly 8s linear infinite;
  image-rendering: pixelated;  /* giữ 8bit sharp */
  filter: drop-shadow(0 0 10px var(--arcane-pink));
  z-index: 100;
}
```

**Nyan PNG:** dùng public domain Nyan Cat sprite (160x40px, 8bit). Codex tìm 1 PNG free hoặc tạo SVG inline.

### 4.14 `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=7860
EXPOSE 7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
```

**Lưu ý HF Spaces:** port mặc định **7860**, không phải 8000.

### 4.15 `requirements.txt`

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
slowapi==0.1.9
beautifulsoup4==4.12.3
lxml==5.3.0
cachetools==5.5.0
jinja2==3.1.4
python-multipart==0.0.12
```

### 4.16 `README.md` (HF Space metadata + intro)

YAML frontmatter (HF Spaces yêu cầu):
```yaml
---
title: Lead Prospector Lite
emoji: 🚀
colorFrom: pink
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: mit
---
```
Body: intro 1 đoạn ngắn, screenshot, link GitHub source.

### 4.17 `.github/workflows/sync-to-hf.yml`

```yaml
name: Sync to HF Space
on:
  push:
    branches: [main]
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          lfs: true
          fetch-depth: 0
      - name: Push to HF Space
        env:
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
        run: |
          git push https://vstream:[email protected]/spaces/vstream/lead-prospector-lite main --force
```
**Setup:** GitHub repo Settings → Secrets → `HF_TOKEN` (write token tạo từ HF account settings).

### 4.18 `.gitignore`
```
__pycache__/
*.pyc
.env
.venv/
venv/
.DS_Store
.local/
*.log
```

### 4.19 `.dockerignore`
```
.git/
.github/
.venv/
__pycache__/
*.pyc
docs/
.gitignore
README.md
```

---

## 5. Quality bar (chất lượng ngang repo gốc)

| Test case | Expected |
|---|---|
| `Nestle Vietnam` + procurement | ≥2 profile có "Procurement" trong title, company chứa "Nestle" |
| `Cong ty CP Cha Phe Trung Nguyen` (có dấu) | Tự fanout không dấu, ra ≥1 profile |
| MST `0301234567` valid | `links.masothue` ra dạng `https://masothue.com/0301234567-slug` |
| MST empty | `links.masothue` ra Google search fallback |
| Company không tồn tại | `profiles: []`, warning "Không tìm thấy" |
| 11 lượt search trong 1 giờ từ cùng IP+cookie | Lượt 11 trả 429 |
| DDG trả captcha | App trả 503 với message Vietnamese |

---

## 6. Out of scope (KHÔNG làm)

- LinkedIn direct scrape (chỉ DDG).
- Bulk Excel input.
- User account / login.
- History/saved search per user.
- Email outreach generation.
- Pagination DDG (chỉ trang 1).
- Multi-language UI (chỉ Vietnamese).
- Mobile app.
- Analytics tracking (HF Spaces tự track view).

---

## 7. Codex execute checklist

Codex làm theo thứ tự:
1. Tạo folder structure section 3.
2. Port 6 file engine từ control-tower theo section 4.1-4.6 (đường dẫn chính xác trong `SOURCE_REFERENCE.md`).
3. Viết `engine/ddg_client.py` mới (section 4.7).
4. Tạo 3 file config (section 4.8-4.10).
5. Viết `app.py` (section 4.11).
6. Viết `templates/index.html` + `static/style.css` (section 4.12-4.13).
7. Tìm/tạo `static/nyan.png` (160x40 8bit sprite, có thể inline SVG nếu không tìm được PNG free).
8. Viết Dockerfile + requirements + gitignore + dockerignore (section 4.14-4.15, 4.18-4.19).
9. Viết README với YAML frontmatter HF (section 4.16).
10. Viết GitHub Action (section 4.17).
11. Test local: `pip install -r requirements.txt && uvicorn app:app --reload --port 7860` → mở http://localhost:7860 → search test case section 5.
12. Report về `docs/CODEX_REPORT.md` với: file list created, deviations từ blueprint (nếu có), test results, deploy readiness.

**Report mandatory:** kê khai bất kỳ deviation nào so với blueprint này. Không tự ý add feature.
