# Deploy Guide — Lead Prospector Lite

Hướng dẫn user (Vstream) deploy sau khi Codex build xong code.

---

## Bước 1: Test local

```powershell
cd C:\Users\chudu\Downloads\apps\lead-prospector-lite
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload --port 7860
```

Mở `http://localhost:7860`. Test 3 case:
1. `Nestle Vietnam` + procurement → ra ≥2 profile.
2. MST `0301234567` (random valid) → link masothue đúng format.
3. Search 11 lần liên tiếp → lượt 11 báo "Hết lượt".

---

## Bước 2: Tạo GitHub repo

1. Vào github.com → New repository.
2. Name: `lead-prospector-lite`.
3. Visibility: **Public** (HF Spaces sync cần public hoặc trả phí).
4. KHÔNG init README/gitignore (đã có sẵn local).
5. Tạo xong, copy URL `https://github.com/<user>/lead-prospector-lite.git`.

Local push:
```powershell
cd C:\Users\chudu\Downloads\apps\lead-prospector-lite
git init
git add .
git commit -m "feat: initial MVP scaffold"
git branch -M main
git remote add origin https://github.com/<user>/lead-prospector-lite.git
git push -u origin main
```

---

## Bước 3: Tạo Hugging Face Space

1. Đăng nhập huggingface.co (Google/GitHub OAuth).
2. Click avatar góc phải → New Space.
3. Owner: `<user>` (hoặc org Vstream nếu tạo).
4. Space name: `lead-prospector-lite`.
5. License: MIT.
6. Select SDK: **Docker** → Blank template.
7. Hardware: CPU basic (free).
8. Visibility: Public.
9. Create Space.

Sau khi tạo, URL Space: `https://huggingface.co/spaces/<user>/lead-prospector-lite`.
URL public app: `https://<user>-lead-prospector-lite.hf.space`.

---

## Bước 4: Setup GitHub Action sync sang HF

### 4a. Tạo HF write token
1. HF profile → Settings → Access Tokens → New token.
2. Name: `github-action-sync`.
3. Type: **Write**.
4. Copy token (dạng `hf_xxxxx...`).

### 4b. Add token vào GitHub secret
1. GitHub repo → Settings → Secrets and variables → Actions → New repository secret.
2. Name: `HF_TOKEN`.
3. Value: paste token.

### 4c. Sửa file `.github/workflows/sync-to-hf.yml`
Mở file, thay `vstream` ở dòng `git push https://vstream:[email protected]/spaces/vstream/...` thành HF username thật của bạn.

Commit + push:
```powershell
git add .github/workflows/sync-to-hf.yml
git commit -m "ci: setup HF Spaces auto-sync"
git push
```

Lần push này sẽ trigger Action lần đầu → check tab **Actions** trên GitHub repo xem có pass không.

---

## Bước 5: Verify deploy

1. Vào Space URL → tab **Logs** xem build (mất 2-3 phút lần đầu vì download base image + install pip).
2. Build xong → tab **App** → giao diện hiện ra.
3. Test search → verify ra kết quả.
4. Test rate limit từ trình duyệt khác (incognito) để xem có chia quota riêng không.

---

## Bước 6: Share link

Public URL dạng: `https://<user>-lead-prospector-lite.hf.space`.

Copy đoạn warning vào caption khi share:
> Demo MVP — mỗi người 10 lượt/giờ. Hệ thống có giới hạn, share xin từ tốn.

---

## Workflow update sau này

```powershell
# Sửa code local
cd C:\Users\chudu\Downloads\apps\lead-prospector-lite
# ... edit files ...

# Commit + push
git add .
git commit -m "fix: <mô tả>"
git push

# GitHub Action tự sync sang HF → HF rebuild ~2-3 phút → URL update
```

KHÔNG cần push tay sang HF, GitHub Action lo.

---

## Troubleshooting

| Triệu chứng | Nguyên nhân | Fix |
|---|---|---|
| HF build fail "port 7860 not exposed" | Dockerfile thiếu EXPOSE hoặc CMD sai port | Check Dockerfile dòng cuối, đảm bảo `--port 7860` |
| GitHub Action fail "authentication required" | HF_TOKEN expired hoặc không phải write | Tạo token mới, update secret |
| Search trả 503 liên tục | DDG block IP HF Space | Đợi 30-60 phút. Nếu lặp lại, add Playwright fallback (xem ROADMAP) |
| Container restart bất thường | HF Space free tier reset sau ~3-7 ngày không hoạt động | Bình thường, cache + rate counter reset theo |
| Không thấy emoji 🚀 trên Space card | YAML frontmatter sai | Check README.md dòng đầu, đảm bảo có 3 dấu `---` |
