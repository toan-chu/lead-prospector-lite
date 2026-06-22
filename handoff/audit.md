# Audit Log — Claude reviews

Mỗi lần user gõ `check` sau khi Codex báo xong, Claude append 1 entry vào đây.

Format:

```
## <date> — Round <N>: <topic>
**Reviewed by:** Claude
**Codex report:** docs/CODEX_REPORT.md (commit <sha>)
**Sampled files:** <list 2-3 file core đã đọc>
**Findings:**
- ...
**Verdict:** approved | needs_fix
**Action items (nếu needs_fix):**
- ...
```

---

<!-- Entries below, newest on top -->

## 2026-06-22 — Round 1: Initial MVP scaffold
**Reviewed by:** Claude
**Codex report:** docs/CODEX_REPORT.md
**Sampled files:** `app.py`, `engine/ddg_client.py`, `engine/dedup_profiles.py`, `templates/index.html`, `config/scoring-rules.json`, `Dockerfile`, `.github/workflows/sync-to-hf.yml`, `.gitignore`, `requirements.txt`, `README.md`.

**Findings:**
- 22/22 checklist tick, structure đúng BLUEPRINT section 3 + thêm `tests/`, `memory/`, `requirements-dev.txt` (deviation đã khai báo, không add feature).
- Contract khớp: `dedup_profiles(list[dict])` simplified đúng; `score_profiles` signature callable từ `app.py`; scoring threshold = 70, exclude list đã thêm Founder/CEO/Chairman.
- Engine port từ control-tower nguyên vẹn (giữ comment debug encoding artifacts trong `score_profiles.py` `_LEGAL_SUFFIX_WORDS` — không ảnh hưởng logic).
- `app.py` middleware order đúng: `ensure_uid_cookie` add trước `SlowAPIMiddleware` → chạy outermost → uid available cho rate limit key.
- Error handling đầy đủ 3 path: `DDGBlocked` → 503, `DDGEmpty` → 200 + warning, `RateLimitExceeded` → 429, tất cả message tiếng Việt.
- Dockerfile port 7860 đúng HF Spaces; YAML frontmatter README đúng format.
- Workflow GitHub Action có `permissions: contents: read` + auth URL chuẩn.

**Fix nhỏ Claude tự apply:**
- Thêm `.pytest_cache/` vào `.gitignore` (Codex bỏ sót, `pytest` đã tạo folder trong root).

**Action items trước khi push:**
- User PHẢI đổi 2 chỗ placeholder `vstream` thành GitHub/HF username thật:
  - `README.md` dòng 29: `https://github.com/vstream/lead-prospector-lite`
  - `.github/workflows/sync-to-hf.yml` dòng 22: `huggingface.co/spaces/vstream/lead-prospector-lite`
- User PHẢI xóa folder `__pycache__/` và `.pytest_cache/` ở root local trước khi git init (tránh commit nhầm — sau khi git init thì `.gitignore` mới có hiệu lực).

**Verdict:** approved (sẵn sàng push GitHub + deploy HF).

## 2026-06-22 15:47 -- Initial MVP scaffold -- REPORT

**Done:** Hoàn tất 22/22 checklist section 7, gồm engine port, FastAPI, frontend, deploy files, test và Codex report.
**Files changed:** `app.py`, `engine/`, `config/`, `templates/index.html`, `static/`, `tests/test_app.py`, deploy/docs/workspace files.
**Verification:** 7/7 pytest pass; compileall, contract invariants, secret scan, health check và browser QA desktop/mobile pass.
**Open questions for Cowork:** Không.
**Risks/known gaps:** Docker không có trên máy nên chưa chạy image build. DDG live có thể block theo IP; app trả 503 đúng contract và giữ nguyên guard.

---

## 2026-06-22 15:25 -- Pre-action note: create Hugging Face sync workflow

**What:** Tạo `.github/workflows/sync-to-hf.yml` đúng blueprint section 4.17.
**Why:** GitHub push lên `main` phải mirror code sang Hugging Face Space.
**Blast radius:** Chỉ workflow mới trong repo; khi được commit/push, workflow có thể force-push nhánh `main` sang Space đích.
**Rollback:** Xóa hoặc revert riêng workflow trước lần push tiếp theo; HF Space vẫn giữ snapshot gần nhất.

---
