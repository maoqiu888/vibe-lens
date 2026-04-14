# V1.0 Manual Smoke Test

## Prereqs
1. Backend running: `cd backend && uvicorn app.main:app --reload --port 8000`
2. Extension built: `cd extension && npm run build`
3. Extension loaded in Chrome via `chrome://extensions` → Load unpacked → `extension/build/`
4. `backend/.env` configured with a real LLM API key (needed for steps 3-10; V1.1 adds roast + recommendation calls that also hit the LLM)

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

### 8. Roast display (V1.1)
- Highlight text on 豆瓣电影 → click icon → wait for rate card
- Expected: a **bold purple roast line** appears as the prominent copy (30-50 chars)
- Below the roast, an **italic grey summary** (smaller) is still visible
- The roast should reference the current domain's metaphor (影院睡着 / 摔手柄 / 翻不过30页 / 塞满棉花)
- If roast cannot generate (backend glitch), the grey summary should promote to primary styling instead — never show an empty card

### 9. Cross-domain recommendation (V1.1)
- Rate something → click the small grey "> 寻找同频代餐" link at the bottom of the card
- Expected: the link disappears, a sub-card appears below with a "代餐官思考中…" placeholder
- After ~2-5 seconds, 3 items appear, each with a distinct domain emoji (📚🎬🎮🎵)
- **None of the 3 items must be from the source domain** — on `movie.douban.com`, zero 🎬 items; on `store.steampowered.com`, zero 🎮 items
- Click "换一批 ↻" → button disables briefly → new 3 items (different from previous)
- If the LLM keeps returning same-domain items, the card should show "这次没灵感，换一个物品试试"

### 10. Share poster (V1.1)
- On a rated card, click the [📤] button in the top-right
- Expected: a mini dialog with three buttons: "📋 复制到剪贴板", "💾 下载 PNG", "取消"
- Click 复制 → a toast "已复制到剪贴板" appears briefly at the bottom of the card
- Open WeChat / mspaint / any image-accepting target and paste → a 1080×1080 PNG with purple gradient background, the match score, tags, roast text, and "Vibe-Radar" wordmark should appear
- Click 下载 → a file named `vibe-radar-<timestamp>.png` downloads; open it to verify the same layout
- If clipboard permission is denied, a toast "剪贴板失败，已自动下载" appears and the file downloads automatically

## Pass criteria
All 10 steps complete without any JavaScript console errors in either the background worker or the content script.
