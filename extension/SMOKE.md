# V1.0 Manual Smoke Test

## Prereqs
1. Backend running: `cd backend && uvicorn app.main:app --reload --port 8000`
2. Extension built: `cd extension && npm run build`
3. Extension loaded in Chrome via `chrome://extensions` → Load unpacked → `extension/build/`
4. `backend/.env` configured with a real LLM API key (only needed for step 4)

## Steps

### 1. Cold start
- Click extension icon → popup shows 18 cards (6 categories × 3 each)
- Click one card per category → bottom button reads "开始鉴定" and becomes purple
- Click → popup switches to radar chart view
- Expected: 6-axis radar, 4 categories at ~0, 6 categories at ~42 (one tier-1 each, core_weight=15)

### 2. Popup reopens to radar
- Close popup, reopen → goes directly to radar view (not cold-start)
- `chrome.storage.local.profile_initialized` should be `true`

### 3. Highlight-to-analyze — basic
- Go to `https://book.douban.com/subject/1000000/` (any Douban book)
- Highlight 2-10 Chinese characters in any review
- Expected: a round purple icon appears at the top-right of the selection
- Click the icon → rounded card appears below with:
  - Large match score percentage
  - One-line AI summary
  - Purple pill-shaped tags
  - 💎 懂我 / 💣 踩雷 buttons

### 4. Star/Bomb flow
- Click 💎 → button text becomes "✓ 已确权" → card fades after 1.5s
- Open popup → radar values should have shifted (same-tag categories +10)

### 5. Cache hit
- Highlight the exact same text a second time → click icon again
- Check background service worker console: should log `cache_hit: true` (visible in network response)
- Observably, response arrives faster than the first call

### 6. Backend-down handling
- Stop uvicorn
- Highlight text → click icon
- Expected: card shows "后端未运行，请先启动 FastAPI" and disappears after 3s

### 7. Out-of-whitelist sites
- Go to `https://www.baidu.com/`
- Highlight any text
- Expected: no icon appears (content script not injected)

## Pass criteria
All 7 steps complete without any JavaScript console errors in either the background worker or the content script.
