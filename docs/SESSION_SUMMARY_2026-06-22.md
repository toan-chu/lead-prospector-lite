# Session Summary — 2026-06-22

**Purpose:** Tài liệu handoff cho chat session tiếp theo. Đọc file này để pick up mạch logic không mất context.

---

## 1. Mục tiêu sản phẩm

**What:** Web app demo MVP cho non-tech (Sales/BD). Input 1 tên công ty (+ optional MST + role dropdown) → output 3 best LinkedIn profile + 3 link bổ sung (masothue, Google website, Google company).

**Why:** Demo hội thảo + tặng bạn Vstream dùng. Mục tiêu "wow" cho non-tech.

**Persona:** Sales/BD nhỏ lẻ, không biết Boolean search, dùng trên điện thoại/laptop, click URL là xong.

**Origin:** Snapshot fork từ `control-tower/skills/lead-prospector/` (Vstream internal platform).

---

## 2. Architecture đã build (Round 1 — DONE)

**Stack:**
- Backend: FastAPI 0.115 + slowapi (rate limit) + cachetools (TTL 24h) + BeautifulSoup4 (HTML parse) + urllib (no Playwright)
- Frontend: Vanilla HTML/CSS/JS (1 file, no React, no build step)
- Container: Docker (Python 3.12-slim)
- Host: Hugging Face Spaces (Docker SDK, free CPU)
- CI/CD: GitHub Action auto sync `github.com/toan-chu/lead-prospector-lite` → `huggingface.co/spaces/toanchu/lead-prospector-lite`

**File structure (port + new):**
```
lead-prospector-lite/
├── app.py                          # FastAPI: 3 endpoints (/, /api/search, /api/status)
├── engine/
│   ├── build_search_query.py       # Port từ control-tower (đã bỏ LinkedIn direct + fanout)
│   ├── extract_web_search_results.py  # Port nguyên 365 LOC parse DDG HTML
│   ├── score_profiles.py           # Port nguyên 583 LOC Boolean matcher
│   ├── dedup_profiles.py           # Simplified (bỏ knowledge file scan)
│   ├── url_utils.py                # Port từ shared/tools/
│   ├── validate_boolean.py         # Port nguyên
│   └── ddg_client.py               # NEW — urllib + UA rotation + 2-4s delay + block detection
├── config/
│   ├── scoring-rules.json          # threshold 70 (raise từ 50), exclude mở rộng (thêm Founder/CEO/Chairman)
│   ├── title-synonyms.json         # Port nguyên
│   └── role-presets.json           # NEW — 4 role dropdown Procurement/Sales/Logistics/Supply Chain
├── static/
│   ├── style.css                   # Arcane neon theme (purple #4a1c5e + pink #ff1493 + cyan #00d4ff)
│   └── nyan.png                    # 8bit cat sprite (160x40, Codex tự gen)
├── templates/
│   └── index.html                  # Google-style center form + result cards
├── tests/test_app.py               # 7 pytest pass
├── docs/                           # BLUEPRINT, SOURCE_REFERENCE, DEPLOY, AGENTS, CODEX_REPORT
├── handoff/                        # todo.md (round work), audit.md (Claude review)
├── log/                            # history.md (milestones), failure.md (lessons)
├── .github/workflows/sync-to-hf.yml  # Auto push GitHub → HF Space
├── Dockerfile                      # python:3.12-slim + uvicorn port 7860 + --proxy-headers
├── requirements.txt                # Pinned versions
├── README.md                       # YAML frontmatter HF (title, emoji, sdk: docker, port 7860)
└── LICENSE                         # MIT
```

**Key contract:**
- `POST /api/search` body `{company, mst?, role}` → returns `{profiles[3], links{masothue,google_website,google_company}, rate_limit, warnings}`
- Rate limit: 10/hour keyed by `IP+cookie_uid`
- Cache: `(company_normalized, role)` → TTL 24h
- Cat: top-right badge, wiggle nhẹ tại chỗ. Trail rainbow 90px sau đuôi cat (round 3 final).

---

## 3. Decisions đã chốt qua trao đổi

| Decision | Final value | Lý do |
|---|---|---|
| Deploy target | HF Spaces (Docker SDK) | Free, không cold start, public URL |
| Search engine | DDG → **đang tìm replacement** | DDG block IP HF Space (xem section 5) |
| Browser strategy | urllib only (no Playwright) | MVP nhẹ, Playwright fallback Round 2 nếu cần |
| Title input | Dropdown 4 role preset (Procurement/Sales/Logistics/Supply Chain) | Non-tech dễ dùng |
| Output count | 3 profile best | Tránh nhiễu, chất lượng > số lượng |
| Score threshold | 70 (raise từ 50) | Strict hơn để catch right profile |
| Rate limit | 10/hour (IP + cookie) | Chống abuse + DDG quota |
| Cache TTL | 24h | Giảm tải DDG đáng kể |
| UI theme | Arcane neon (purple+pink+cyan) + Nyan Cat | Wow factor |
| Repo strategy | Tách riêng `lead-prospector-lite`, KHÔNG nhét vào control-tower | Snapshot fork, độc lập, public OK |
| Workflow | GitHub Desktop local-first → Publish → GitHub Action sync HF | Tránh lỗi tạo online trước không connect được |

---

## 4. URLs sống hiện tại

- GitHub repo: `https://github.com/toan-chu/lead-prospector-lite` (public, có Initial commit + 4-5 commits sau)
- HF Space: `https://huggingface.co/spaces/toanchu/lead-prospector-lite` (Running, build OK)
- App URL: `https://toanchu-lead-prospector-lite.hf.space` (UI render OK sau Mixed Content fix)
- Username: GitHub `toan-chu` (có dash), HF `toanchu` (KHÔNG dash) — **lưu ý đừng nhầm**

---

## 5. Issue discovered & status

### 5.1 Mixed Content (FIXED Round 1.5)
**Symptom:** UI trắng bóc khi mở HF Space (Nyan + Form render nhưng không có Arcane theme).
**Root cause:** FastAPI `url_for` render link CSS với scheme `http://` (do uvicorn không trust proxy header `X-Forwarded-Proto` từ HF reverse proxy). Browser block stylesheet vì page load HTTPS. Image OK vì Mixed Content rule chỉ warn image, BLOCK stylesheet.
**Fix:** Sửa Dockerfile CMD thêm `--proxy-headers --forwarded-allow-ips=*`.
**Status:** ✅ Fixed, commit `fix: trust proxy headers cho url_for ra https`.

### 5.2 Nyan animation pattern (FIXED Round 3)
**Iterations:**
- Round 1 (Codex initial): Rainbow trail bay theo cat (snake trail mèo bay full-width) → user reject
- Round 2 attempt: Cat phải→trái + rainbow static full-width → user reject "chạy ngang qua box"
- Round 3 attempt: Cat trái→phải + rainbow GROW theo cat (scaleX 0→1) → user reject "chạy căng ngang"
- **Round 3 FINAL: Cat → loading badge cố định góc phải, wiggle tại chỗ. Trail rainbow ngắn 90px sau đuôi cat, floating cùng wiggle. Khi searching: wiggle nhanh hơn + trail dài hơn → loading indicator.**

**Status:** Code đã sửa, 2 file (`static/style.css`, `templates/index.html`) **PENDING COMMIT** (đang ở Changes tab Desktop chưa push).

### 5.3 Error case không clear results (FIXED Round 3)
**Symptom:** Search Vinamilk → 0 profile + links Vinamilk. Sau đó search Masan 503 → links bên dưới vẫn là Vinamilk → confusion.
**Fix:** Sửa JS `showError()` clear `resultsSection`, `profileList`, `linkList`, `latestProfiles[]`.
**Status:** ✅ Fixed cùng commit Round 3, **PENDING COMMIT**.

### 5.4 DDG block IP HF Space (BLOCKER, chưa fix)
**Symptom:** Search Masan/Trustana/cty bất kỳ → 503.
**Log evidence (sau khi add logging):**
```
DDG fetch ok bytes=14452
DDG block marker matched=bots use duckduckgo too
INFO: 123.21.108.107:0 - "POST /api/search HTTP/1.1" 503 Service Unavailable
```
**Root cause:** DDG trả HTTP 200 nhưng content là challenge page "Bots use DuckDuckGo too". DDG rate-limit IP server-hosted (HF datacenter range) trong 1-2 query/phút.
**Vinamilk lần đầu pass:** Có thể vì query đơn giản hơn hoặc DDG chưa kịp flag. Sau đó tất cả query block.
**Status:** ⚠️ KHÔNG fix được bằng technical tuning. Cần replace search engine (xem section 6).

---

## 6. Decisions đang OPEN (user đang nghĩ)

### Search engine alternative đã evaluate:

| Provider | Free tier | Card | Setup status |
|---|---|---|---|
| **Google Custom Search API** | 100/ngày = 3000/tháng | ❌ Không cần | ⚠️ Setup 45 phút FAIL. Project `lead-prospector-lite` đã enable Custom Search API, key `lead-prospector-cse-2` tạo OK, test URL vẫn 403 "project does not have access". Có khả năng key bind nhầm project. **PAUSED** chưa giải quyết. |
| **Brave Search API** | 1000/tháng credit $5 | ✅ Cần card verify | Chưa thử |
| **Tavily Search API** | 1000/tháng | ❌ Không cần | Chưa thử |
| **Playwright fallback trong HF** | Free | — | Heavy image 1.2GB, có thể OOM HF free |
| **Hybrid PC bạn host + tunnel** | Free | — | Phụ thuộc PC online 24/7 |
| **Compile desktop .exe local** | Free | — | User pivot vừa propose, đang nghĩ |

### Credentials đã có (lưu ý: leak chat, đã rotate hoặc cần rotate):

- **Google API key 1:** `AIzaSyAcXGrWnBxgDq95XJuqXcgCXN059VRTaBU` (LEAK chat, key cũ — user nói tài khoản rác không lo)
- **Google API key 2:** `AIzaSyAvKG1MUpKnj_phdrFOwI3G8GruUTGt4-E` (LEAK chat, key mới — vẫn fail 403)
- **CSE ID:** `41d865c2b89394a4e` (public OK, restrict `linkedin.com/in/*`)

### Pivot user đang cân nhắc (chat cuối):

> "Chắc là nghĩ tới compile thôi, chứ web ko ổn. Compile để user tự tải về máy tự chạy = local playwright"

→ User cân nhắc bỏ web/HF Space, làm desktop .exe có Playwright embedded.

**Compile approach effort:**
- Re-add Playwright + persistent profile: ~150 LOC port từ control-tower
- PyInstaller spec bundle Chromium: 1-2h debug
- Auto-open browser: ~20 LOC
- Build .exe Windows: ~30 phút
- Total: 4-5h Codex
- File size: ~250MB
- Pain points: Windows Defender flag false positive, Mac/Linux mỗi platform riêng, update flow phải redownload

---

## 7. Round commits đã push

```
* main HEAD
* fix: add DDG logging + rainbow static + cat flying    (pending push? Cần check)
* fix: trust proxy headers cho url_for ra https
* ci: add manual workflow dispatch + retry sync
* chore: set real github + hf usernames
* ci: setup HF Spaces auto-sync (first sync trigger)
* Initial commit                                         (Desktop tự tạo từ folder có sẵn)
```

**Pending uncommitted (lúc move folder):**
- `static/style.css` — Round 3 final: cat → loading badge wiggle góc phải
- `templates/index.html` — JS clear results on error

---

## 8. Folder location

**Cũ:** `C:\Users\chudu\Downloads\apps\lead-prospector-lite\` + `C:\Users\chudu\Downloads\apps\control-tower\`

**Mới (sau move):** `D:\apps\lead-prospector-lite\` + `D:\apps\control-tower\`

**Files có hardcode path cũ cần find-replace nếu muốn sạch:**
- `docs/BLUEPRINT.md`
- `docs/SOURCE_REFERENCE.md`
- `docs/DEPLOY.md`

Find-replace `C:\Users\chudu\Downloads\apps` → `D:\apps` trong VSCode (Ctrl+Shift+H).

---

## 9. Mở chat mới — instruction cho Claude tiếp theo

**Hand-off khi user mở chat mới:**

1. **Mount folder:** `D:\apps\lead-prospector-lite\` (chat này đã được mount, user xác nhận).
2. **Đọc file này:** `docs/SESSION_SUMMARY_2026-06-22.md` ngay tin đầu tiên để có context.
3. **Đọc đính kèm:** `docs/BLUEPRINT.md` (spec gốc) + `handoff/audit.md` (Claude review) + `log/history.md` (milestone).
4. **Verify status:** check `git log --oneline` + tab Changes Desktop xem pending commit gì.
5. **Pick up từ decision point:** user đang nghĩ giữa 2 option:
   - **Option A:** Compile desktop .exe local với Playwright (pivot lớn, bỏ web).
   - **Option B:** Tiếp tục web HF + thử thêm 1 search API alternative (Tavily, Brave, hoặc retry Google CSE với project mới).

**Câu hỏi đầu tiên Claude tiếp theo nên hỏi user:**
"Bạn đã quyết hướng nào — desktop .exe hay tiếp tục web với search API mới? Hay vẫn đang nghĩ?"

---

## 10. User preferences ghi nhớ

- Tiếng Việt, thuật ngữ kỹ thuật giữ English.
- Concise mặc định, không filler.
- Phản biện thẳng nếu user sai, đưa alternative.
- Token bóp được thì bóp.
- Phân vai: Claude (Cowork) = blueprint + audit + light scaffolding. Codex = execute heavy. Quyết định lớn trao đổi trước.
- Quantify diff bằng số liệu (LOC, file count, %), không rate "tốt/xấu".
