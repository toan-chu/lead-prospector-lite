# Agents Instructions — Lead Prospector Lite

Quy ước cho agent (Codex, Claude) khi làm việc trong repo này.

## Vai trò

- **Claude (Cowork)** = blueprint, audit, review. Đã viết xong `BLUEPRINT.md` + `SOURCE_REFERENCE.md` + `DEPLOY.md` — đây là spec FROZEN.
- **Codex CLI** = executor. Đọc `BLUEPRINT.md` từ section 1 → section 7, làm theo checklist section 7 theo thứ tự.

## Quy tắc bắt buộc cho Codex

1. **Đọc `log/failure.md` TRƯỚC TIÊN** mỗi round — biết rules đã chốt, tránh lặp lỗi.
2. **Đọc `BLUEPRINT.md` ĐẦY ĐỦ trước khi viết file đầu tiên.** Không skip section.
3. **Đọc `SOURCE_REFERENCE.md`** trước khi copy bất kỳ file engine nào — đường dẫn nguồn chính xác ở đó.
4. **Update `handoff/todo.md`** mỗi khi tick xong 1 item. Append note vào section "Notes" khi gặp blocker/decision.
5. **KHÔNG tự ý add feature** không có trong blueprint. Out of scope section 6 là cứng.
6. **KHÔNG đổi config values** trong section 4.8 (scoring threshold, exclude list) — đã chốt qua trao đổi.
7. **Báo cáo deviation:** mọi sai lệch so với blueprint phải ghi vào `docs/CODEX_REPORT.md` section "Deviations". Lý do bắt buộc.
8. **Test trước khi báo xong:** chạy 7 test case section 5 blueprint. Pass tất cả mới ghi `status: ready_to_deploy` trong report.
9. **Sau khi xong:** append 1 dòng vào `log/history.md` (format YYYY-MM-DD | Codex | <event>). Nếu vấp lỗi đáng kể → append rule vào `log/failure.md`.

## Quy tắc khi Claude review (sau khi Codex báo xong)

User gõ `check` → Claude:
1. Đọc `docs/CODEX_REPORT.md` xem deviations.
2. Đọc `handoff/todo.md` confirm 22 item đã tick.
3. Sample 2-3 file core (`app.py`, `extract_web_search_results.py`, `templates/index.html`) verify ko bị Codex đơn giản hóa sai.
4. Verify `requirements.txt` đúng version pinned.
5. Verify YAML frontmatter trong README đúng format HF.
6. Append entry vào `handoff/audit.md` theo format có sẵn.
7. Kết luận: `approved` hoặc `needs_fix` với danh sách concrete.

## Folder convention

```
lead-prospector-lite/
├── docs/         ← spec freeze (Claude write, Codex read)
├── handoff/      ← live round work
│   ├── todo.md   ← checklist round hiện tại (Codex tick)
│   └── audit.md  ← Claude reviews append-only
├── log/          ← project memory
│   ├── history.md   ← milestone log append-only
│   └── failure.md   ← lessons learned, đọc đầu mỗi round
└── <project code>
```

Tất cả 4 file này **commit cố ý** — là work memory giữa Claude và Codex, người clone về thấy được "đã làm gì, vì sao".

## Conventions

- **Tiếng Việt** trong UI, comments, commit messages, docs. Thuật ngữ kỹ thuật giữ English.
- **Code Python**: type hint, async cho I/O, không print() (dùng logging).
- **Commit message**: `feat:` / `fix:` / `chore:` / `docs:` / `ci:` prefix.
- **Không commit secrets**: `.env`, HF token, GitHub PAT. Check `.gitignore` trước mỗi commit.

## Workflow sync với control-tower (sau này)

Khi control-tower có update engine cần đồng bộ:
1. User chỉ Claude qua đọc file source mới.
2. Claude viết patch diff vào `docs/SYNC_<date>.md`.
3. Codex apply patch.
4. Test lại section 5 blueprint.
5. Commit `sync: <file> from control-tower @ <date>`.
