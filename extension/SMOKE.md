# V1.2 Manual Smoke Test

## Prereqs
1. Backend venv installed and active
2. `backend/.env` configured with a real LLM API key (needed for most steps; V1.1 added roast + recommendation calls, V1.2 is mostly backend-internal but still uses roast)
3. Chrome with developer mode enabled

## Step 0: Reset database (V1.2 required, one-time)
V1.2 changed the `users` table schema (added `interaction_count`). You MUST delete the old DB and re-seed before any smoke step:
```bash
cd D:/qhyProject/vibe4.0/backend
rm data/vibe_radar.db
source .venv/Scripts/activate
python -m app.services.seed
```
This rebuilds the schema and reinserts the 24 vibe tags. `user_id=1` will be lazy-created on first analyze.

## Start services
```bash
cd D:/qhyProject/vibe4.0/backend
source .venv/Scripts/activate
uvicorn app.main:app --reload --port 8000
```

```bash
cd D:/qhyProject/vibe4.0/extension
npm run build
```

Chrome → `chrome://extensions` → Developer mode → Load unpacked → `extension/build/`

---

## Steps

### 1. Welcome page (V1.2)
- Click the extension icon → popup opens
- Expected: you see a **welcome page** (no 18 cards, no radar) with logo, tagline "我会通过你的真实行为认识你", and a 4-item grid of supported sites
- Close the popup

### 2. First-interaction cold start (V1.2)
- Go to `https://book.douban.com/subject/1000000/` (any Douban book)
- Highlight 2-10 Chinese characters
- Click the purple icon
- Expected: a **level-up animation** plays for ~1.5 seconds showing:
  - Old emoji (👤) floating up and fading
  - Arrows (↓ ↓ ↓)
  - New emoji (🌱) popping in at larger size
  - Title "Lv.1 初遇"
  - Subtitle "🎉 你已经喂了 1 个信号"
- After the animation, the vibe card renders with:
  - **No percentage number** (learning stage)
  - A **learning badge** showing "🌱 Lv.1 初遇" + "学习中 · 第 1 次"
  - Normal roast text
  - Normal tags
  - Normal 💎/💣 buttons

### 3. Popup reopens with radar + level panel (V1.2)
- Open the popup again
- Expected: no longer shows welcome — instead shows a sparse radar chart (mostly zero values — you only had one interaction) AND a level panel at the bottom with:
  - "🌱 Lv.1 初遇"
  - A progress bar (mostly empty — 0/3 until L2)
  - "已喂入 1 个信号 · 下一级还差 3 次"

### 4. Highlight 3 more times → Lv.2 level-up (V1.2)
- Go back to a supported site, highlight and rate 3 more times
- On the 4th rate, expected: a new level-up animation plays showing L1→L2 transition, emoji 🌿, title "浅尝"
- After the animation, vibe card still shows no percentage (L2 is still "learning" stage)

### 5. Continue to count 16 → unlock percentage display (V1.2)
- Continue highlighting and rating until `interaction_count == 16`
- On the 16th rate, expected: level-up animation shows L3→L4 transition, emoji 🔍, title "入门"
- After the animation, vibe card now SHOWS the percentage number + a small "🔍 Lv.4 入门" hint below it. This is the first level where the match score is visible.

### 6. Highlight-to-analyze cache hit (from V1.1)
- Highlight the exact same text a second time → click icon
- Expected: cache_hit is true in the background worker log, response arrives faster

### 7. Backend-down handling (from V1.0)
- Stop uvicorn
- Highlight text → click icon
- Expected: error card shows "后端未运行，请先启动 FastAPI", disappears after 3s

### 8. Roast display (from V1.1)
- After rating something, expected: bold purple roast line is prominent, grey italic summary below

### 9. Cross-domain recommendation (from V1.1)
- Click "> 寻找同频代餐" link → 3 items with distinct domain emoji appear, none from source domain
- Click "换一批 ↻" → new items appear

### 10. Share poster (from V1.1)
- Click [📤] → dialog with 复制 / 下载 / 取消
- Copy → paste into mspaint → 1080x1080 purple gradient poster
- Download → PNG file

### 11. Impulsive click gives small curiosity delta (V1.2)
- Make sure `interaction_count >= 1` (not first-impression path)
- Highlight a text → IMMEDIATELY click the icon (aim for under 500ms between text selection and icon click)
- After rating, inspect the database:
```bash
cd D:/qhyProject/vibe4.0/backend
sqlite3 data/vibe_radar.db "SELECT action, delta FROM action_log ORDER BY id DESC LIMIT 5;"
```
- Expected: the most recent `analyze` row has `delta=0.15` (0.3× baseline)

### 12. Careful star gives bigger core delta (V1.2)
- Highlight text → click icon → wait at least 5 seconds reading the vibe card → click 💎
- Inspect DB:
```bash
sqlite3 data/vibe_radar.db "SELECT action, delta FROM action_log ORDER BY id DESC LIMIT 5;"
```
- Expected: the most recent `star` row has `delta=15.0` (1.5× baseline)

### 13. Level-up animation skip button (V1.2)
- Trigger any level-up (easiest: reset DB, then do first analyze)
- As soon as the level-up animation appears, click the × in the top-right corner
- Expected: the animation immediately fades out and the normal vibe card appears

## Pass criteria
All 13 steps complete without any JavaScript console errors in either the background worker or the content script.
