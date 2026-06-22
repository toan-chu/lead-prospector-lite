# Todo — Round 1: Initial MVP scaffold

**Owner:** Codex
**Source spec:** `docs/BLUEPRINT.md` (FROZEN)
**Start:** 2026-06-22 15:25
**Status:** done

---

## Checklist (theo BLUEPRINT.md section 7)

- [x] 1. Tạo folder structure section 3
- [x] 2. Port `engine/build_search_query.py` (xóa LinkedIn functions, fanout)
- [x] 3. Port `engine/extract_web_search_results.py` (sửa import)
- [x] 4. Port `engine/score_profiles.py`
- [x] 5. Port `engine/dedup_profiles.py` (simplify signature)
- [x] 6. Port `engine/url_utils.py` từ shared/tools/
- [x] 7. Port `engine/validate_boolean.py`
- [x] 8. Viết `engine/ddg_client.py` mới
- [x] 9. Tạo `config/scoring-rules.json` (threshold 70, exclude list mở rộng)
- [x] 10. Copy `config/title-synonyms.json`
- [x] 11. Tạo `config/role-presets.json`
- [x] 12. Viết `app.py` (FastAPI, slowapi, cache, endpoints)
- [x] 13. Viết `templates/index.html` (Google-style, Nyan, Arcane)
- [x] 14. Viết `static/style.css`
- [x] 15. Tạo/tìm `static/nyan.png` (160x40 8bit)
- [x] 16. Dockerfile (port 7860)
- [x] 17. requirements.txt pinned versions
- [x] 18. .gitignore + .dockerignore
- [x] 19. README.md với YAML frontmatter HF
- [x] 20. `.github/workflows/sync-to-hf.yml`
- [x] 21. Test local 7 case (BLUEPRINT section 5)
- [x] 22. Viết `docs/CODEX_REPORT.md` (deviations + test results + status)

---

## Notes (Codex append khi có)

<!-- Append blockers, decisions, deviations gặp giữa chừng ở đây -->

- 2026-06-22 15:25: Bắt đầu execution theo `docs/BLUEPRINT.md` section 7.
- Compliance additions ngoài folder tree frozen: `tests/` theo testing rules và `memory/` skeleton theo global AGENTS.md; sẽ kê khai trong `docs/CODEX_REPORT.md`.
- 2026-06-22 15:47: Hoàn tất 22/22 item. Automated suite pass 7/7; browser QA desktop/mobile pass.

## Test Plan -- Initial MVP

| # | Scenario | Expected | Status |
|---|----------|----------|--------|
| 1 | `Nestle Vietnam` + procurement | >=2 profile Procurement, company chứa Nestle | pass |
| 2 | Công ty có dấu tiếng Việt | Fanout không dấu, ra >=1 profile | pass |
| 3 | MST `0301234567` | Link masothue đúng format | pass |
| 4 | MST trống | Link masothue fallback Google | pass |
| 5 | Công ty không tồn tại | Profiles rỗng và warning tiếng Việt | pass |
| 6 | 11 request cùng IP + cookie | Request 11 trả 429 | pass |
| 7 | DDG trả captcha | API trả 503 và message tiếng Việt | pass |
