# Source Reference — File gốc cần port từ control-tower

**Snapshot date:** 2026-06-22
**Source repo:** `C:\Users\chudu\Downloads\apps\control-tower`

Codex copy nguyên file rồi sửa import path theo hướng dẫn từng file. KHÔNG sửa logic parse/score trừ khi `BLUEPRINT.md` ghi rõ.

---

## File mapping

| Đích (lite) | Nguồn (control-tower) | LOC | Action |
|---|---|---|---|
| `engine/build_search_query.py` | `skills/lead-prospector/engine/build_search_query.py` | 192 | Copy, **xóa** functions: `build_linkedin_query`, `build_linkedin_search_queries`, `build_fanout_queries`. Giữ: `_quote`, `_company_terms`, `_clean_expression`, `_has_vietnamese_diacritics`, `_strip_accents`, `slugify_company_name`, `build_masothue_url`, `_strip_outer_parentheses`, `_split_top_level_or`, `build_web_search_queries`, `build_web_search_query`, `build_fallback_hyperlinks`. |
| `engine/extract_web_search_results.py` | `skills/lead-prospector/engine/extract_web_search_results.py` | 365 | Copy nguyên. Sửa import dòng đầu: `from shared.tools.url_utils import ...` → `from engine.url_utils import normalize_linkedin_profile_url`. Xóa block `try/except ImportError` fallback sys.path. |
| `engine/score_profiles.py` | `skills/lead-prospector/engine/score_profiles.py` | 583 | Copy nguyên. Sửa import nếu có reference `shared.tools` → `engine.`. Đảm bảo function signature `score_profiles(profiles, company, title_keywords, level_keywords=None, config=None, synonyms=None)` callable từ app.py. |
| `engine/dedup_profiles.py` | `skills/lead-prospector/engine/dedup_profiles.py` | 63 | **Đơn giản hóa**: xóa `_seen_urls`, `_iter_json_profiles`. Signature mới `def dedup_profiles(profiles: list[dict]) -> list[dict]` — chỉ dedup trong batch. |
| `engine/url_utils.py` | `shared/tools/url_utils.py` | xem file | Copy nguyên. Đây là file chia sẻ giữa các skill trong control-tower. |
| `engine/validate_boolean.py` | `skills/lead-prospector/engine/validate_boolean.py` | 59 | Copy nguyên. Không sửa. |
| `config/title-synonyms.json` | `skills/lead-prospector/config/title-synonyms.json` | — | Copy nguyên file JSON. |

## File KHÔNG port (out of scope)

- `batch_runner.py` (880 LOC) — batch state, resume, pause: không cần single-search.
- `read_input.py` (193) — Excel input.
- `generate_output.py` (393) — Excel output + knowledge draft.
- `extract_linkedin_results.py` (357) — LinkedIn direct scrape, không dùng.
- `extract_serp_results.py` (238) — Google SERP, không dùng.
- `replay.py` (130) — replay fixtures, dev tool.
- `action_logger.py` (59) — observability cho batch.
- `clean_company_name.py` (127) — dùng trong batch pipeline, lite có thể inline simple normalize.
- `live_smoke.py`, `dump_fixtures.py`, `mst_search.py` — dev tools.
- `shared/tools/web-search-browser.py` (167) — Playwright wrapper. Lite không dùng Playwright, tự viết `ddg_client.py` urllib.
- Toàn bộ `prompts/`, `templates/` của skill — không dùng LLM.

## Nguyên tắc khi sync lại sau này

Khi control-tower có update lớn, Claude sẽ đọc diff:
1. Nếu fix nằm trong 1 trong 6 file đã port → patch sang lite.
2. Nếu là feature mới của control-tower (batch, LinkedIn direct) → bỏ qua, không relevant.
3. Nếu là refactor architecture → đánh giá có cần follow không, mặc định KHÔNG.

Update method: copy file mới đè file cũ, sửa lại import nếu cần, chạy test case `BLUEPRINT.md` section 5. Nếu pass → commit với message `sync: <file> from control-tower @ <commit-sha>`.
