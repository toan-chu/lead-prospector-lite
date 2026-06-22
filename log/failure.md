# Failure Rules — Lessons Learned

Mỗi lần dự án vấp lỗi đáng kể, append 1 rule ngắn vào đây. Đọc file này TRƯỚC khi bắt đầu work mỗi round để tránh lặp lại.

Format:

```
## <date> — <rule short name>
**Triệu chứng:** ...
**Root cause:** ...
**Rule:** ...
```

---

<!-- Entries below, newest on top -->

## 2026-06-22 — DDG block từ IP server
**Triệu chứng:** N/A — pre-emptive rule.
**Root cause:** DDG block theo IP. App deploy trên HF Space → tất cả user share 1 IP → block đồng loạt.
**Rule:** Luôn giữ rate limit 10/hour/(IP+cookie) + cache 24h + UA rotation + 2-4s delay. KHÔNG remove các guard này dù "thấy chưa block bao giờ".
