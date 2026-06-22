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

# Lead Prospector Lite

Lead Prospector Lite là web app một trang giúp Sales/BD tìm tối đa 3 LinkedIn PIC relevant nhất cho một công ty, kèm liên kết tra cứu mã số thuế và website. App dùng DuckDuckGo HTML, scoring deterministic và không scrape trực tiếp LinkedIn.

![Lead Prospector Lite screenshot](docs/screenshot.png)

## Chạy local

```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 7860
```

Mở `http://localhost:7860`.

## Source

GitHub source: `https://github.com/toan-chu/lead-prospector-lite`
