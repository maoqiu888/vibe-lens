# Vibe-Radar V1.0 设计文档

> 状态：草案（已通过头脑风暴确认）
> 日期：2026-04-14
> 作者：产品负责人 + Claude Code
> 范围：V1.0 最小闭环，单机单用户

---

## 1. 产品定位与范围

### 1.1 定位

**Vibe-Radar 是一款划词式防坑鉴定 Chrome 插件。** 用户在支持的内容平台（豆瓣书/豆瓣电影/Steam/网易云音乐）划中一段文字，插件提取其"Vibe"（情绪/气质标签），对比用户的个性化审美画像，返回匹配度与 AI 侧写，帮用户快速判断"这东西适不适合我"。

核心卖点：**抵抗水军污染，抵抗大众评分偏见，只回答"对你来说值不值"这一个问题。**

### 1.2 V1.0 范围（最小闭环）

做：
- 冷启动：18 张代表作卡片（6 大类 × 每类 3 张），用户必选 6 张初始化画像
- 划词鉴定：mouseup 触发 → Shadow DOM 悬浮图标 → 点击展开鉴定卡片（匹配度 + AI 侧写）
- 态度确权：💎 懂我 / 💣 踩雷 两个按钮，显著修改画像权重
- Popup 雷达图：ECharts 六边形雷达图展示当前画像
- 域识别：URL 白名单命中即激活（book/movie/game/music）

不做（V1.1+）：
- 精选池推荐（方案 β 的第二阶段，独立物品库 + 召回排序）
- 多用户 / 注册登录 / JWT（V1.0 localhost 单用户，写死 `user_id=1`）
- 云端部署 / 跨设备同步
- 画像回滚 / 撤销确权
- 兜底手选域识别
- 前端自动化测试
- 多用户并发

### 1.3 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.10+, FastAPI, SQLAlchemy, SQLite |
| 插件 | Chrome Extension Manifest V3, TypeScript, esbuild |
| 图表 | ECharts（仅打包到 popup） |
| LLM | DeepSeek / Claude Haiku / OpenAI 任选，通过 env 切换 |
| 测试 | pytest（后端），手动冒烟清单（前端） |

---

## 2. 系统架构

### 2.1 架构图

```
┌─────────────────────┐
│   宿主网页           │
│   (豆瓣/Steam/网易云) │
└──────────┬──────────┘
           │ 划词 mouseup
           ▼
┌─────────────────────────────────────┐
│   Content Script (Shadow DOM 隔离)   │
│   - 监听选区 / 域识别                 │
│   - 渲染悬浮图标 + 鉴定卡片            │
└──────────┬──────────────────────────┘
           │ chrome.runtime.sendMessage
           ▼
┌─────────────────────────────────────┐
│   Background Service Worker         │
│   - 统一 API Gateway                │
│   - fetch → localhost:8000          │
└──────────┬──────────────────────────┘
           │ HTTP
           ▼
┌─────────────────────────────────────┐
│   FastAPI (localhost:8000)          │
│   ├─ routers/  (cold-start/vibe/profile) │
│   ├─ services/ (llm_tagger / profile_calc / seed) │
│   ├─ models/   (SQLAlchemy)          │
│   └─ schemas/  (Pydantic)            │
└──────────┬──────────────────────────┘
           │
           ▼
┌────────────────────┐   ┌─────────────────────┐
│   SQLite           │   │   LLM API           │
│   (vibe_radar.db)  │   │  (DeepSeek/Claude)  │
└────────────────────┘   └─────────────────────┘
                                ▲
                                │ 缓存未命中才调用
                          ┌─────┴─────┐
                          │ analysis_ │
                          │  cache 表  │
                          └───────────┘

┌─────────────────────┐
│   Popup (独立页面)   │
│   - 冷启动 18 卡片    │
│   - 雷达图 (ECharts) │
└──────────┬──────────┘
           └→ 与 content 共用 background gateway
```

### 2.2 三条硬规范

1. **Content Script 零 fetch**：所有网络请求通过 `chrome.runtime.sendMessage` 发送给 background，由 background 统一转发，避免跨域/CSP 问题。
2. **Shadow DOM 注入**：content 在宿主网页注入的所有 UI 必须挂在 `attachShadow({mode:'open'})` 下，防止双向 CSS 污染。
3. **ECharts 仅 Popup**：不在 content script 中引入 ECharts（不走 CDN，也不打包进 content bundle）；雷达图只出现在 popup 页面。

---

## 3. 数据模型

### 3.1 标签体系（24 个元标签，6 大类 × 4 档）

档位从 1 到 4 代表强度递进，同类内档 1↔档 4、档 2↔档 3 互为反义。

| 大类 (category) | 档 1 | 档 2 | 档 3 | 档 4 |
|---|---|---|---|---|
| 节奏 (pace) | 慢炖沉浸 | 张弛有度 | 紧凑推进 | 爆裂快切 |
| 情绪色调 (mood) | 治愈温暖 | 明亮轻快 | 忧郁内省 | 黑暗压抑 |
| 智力负载 (cognition) | 放空友好 | 轻度思考 | 烧脑解谜 | 认知挑战 |
| 叙事质感 (narrative) | 白描克制 | 细腻抒情 | 奇观堆砌 | 解构实验 |
| 世界感 (world) | 日常烟火 | 奇幻异想 | 赛博机械 | 历史厚重 |
| 情感浓度 (intensity) | 轻食小品 | 有共鸣 | 情感重击 | 灵魂灼烧 |

### 3.2 数据库表结构（SQLite）

#### `vibe_tags` — 标签种子表
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK | 1-24 |
| name | TEXT | "慢炖沉浸" |
| category | TEXT | "pace" |
| tier | INT | 1-4 |
| opposite_id | INT FK→vibe_tags.id | 逆向标签 id |
| description | TEXT | LLM prompt 里作为定义句 |

#### `users` — 用户表（V1.0 只有一条 `id=1`）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK | |
| username | TEXT | V1.0 写死 "default" |
| created_at | DATETIME | |

#### `user_vibe_relations` — 双权画像表（核心）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK | |
| user_id | INT FK | |
| vibe_tag_id | INT FK | |
| curiosity_weight | FLOAT | 默认 0，每次划词命中 +0.5 |
| core_weight | FLOAT | 默认 0；冷启动 +15；💎 +10；💣 -10 |
| updated_at | DATETIME | |

唯一索引 `(user_id, vibe_tag_id)`。冷启动时对每个 tag 各 INSERT 一条（24 条），后续只 UPDATE。

#### `analysis_cache` — LLM 缓存表
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK | |
| text_hash | TEXT UNIQUE | SHA256(trim(text) + domain) |
| domain | TEXT | "book"/"game"/"movie"/"music" |
| tags_json | TEXT | LLM 返回的 `{"tags":[{tag_id,weight}],"summary":"..."}` |
| summary | TEXT | 冗余存一份便于查询 |
| created_at | DATETIME | TTL 7 天（查询时过滤） |
| hit_count | INT | 监控命中率 |

#### `action_log` — 操作审计日志
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK | |
| user_id | INT FK | |
| vibe_tag_id | INT FK | |
| action | TEXT | "star" / "bomb" / "cold_start" / "analyze" |
| delta | FLOAT | 本次对权重的增量 |
| target_column | TEXT | "core" / "curiosity" |
| created_at | DATETIME | |

V1.0 只写不读；为 V1.1 的"撤销/回溯"预留。

### 3.3 匹配度计算公式

```
effective_weight[tag_i] = core_weight[i] * 1.0 + curiosity_weight[i] * 0.3

item_vec = 24 维，LLM 返回的 tag_id → weight，其余为 0
user_vec = 24 维的 effective_weight

match_score = cosine_similarity(item_vec, user_vec) * 100
```

`core` 系数是 `curiosity` 的约 3 倍，对应"灵魂确权优先于好奇心波动"的产品直觉。V1.0 权重无上下限（不做 clip），V1.1 考虑 `core_weight ∈ [-100, 100]`。

### 3.4 雷达图数据归一化

每个 category 的 score：
```
score = Σ(tier_i × effective_weight_i) / max_possible_in_category
```
映射到 0-100。雷达图 6 个顶点对应 6 个 category，不直接展示 24 个 tag（会太花）。

---

## 4. 后端 API

### 4.1 目录结构

```
backend/
├── app/
│   ├── main.py              # FastAPI 入口 + CORS
│   ├── config.py            # 环境变量（LLM_API_KEY, DB_PATH, LLM_MODEL, LLM_PROVIDER）
│   ├── database.py          # SQLAlchemy engine + SessionLocal
│   ├── models/
│   │   ├── user.py
│   │   ├── vibe_tag.py
│   │   ├── user_vibe_relation.py
│   │   ├── analysis_cache.py
│   │   └── action_log.py
│   ├── schemas/
│   │   ├── cold_start.py
│   │   ├── analyze.py
│   │   └── action.py
│   ├── routers/
│   │   ├── cold_start.py
│   │   ├── vibe.py          # /analyze + /action
│   │   └── profile.py       # /radar
│   ├── services/
│   │   ├── llm_tagger.py    # 调 LLM + 缓存
│   │   ├── profile_calc.py  # 匹配度 + 权重更新
│   │   └── seed.py          # 灌 24 标签 + 18 冷启动卡片
│   └── deps.py              # get_db, get_current_user（V1.0 写死 user_id=1）
├── data/
│   └── vibe_radar.db
├── tests/
│   ├── test_cold_start.py
│   ├── test_analyze.py
│   ├── test_action.py
│   ├── test_profile_calc.py
│   └── test_integration.py  # 标记 @pytest.mark.integration，默认不跑
├── requirements.txt
└── README.md
```

### 4.2 API 契约

基础约定：
- 所有接口前缀 `/api/v1`
- V1.0 无 JWT，所有接口默认 `user_id=1`（`deps.get_current_user` 返回固定值）
- 统一错误格式：`{"error": {"code": "...", "message": "..."}}`
- CORS 白名单：开发期放开 `*`；V1.1 收紧为 `chrome-extension://<EXT_ID>`

#### 4.2.1 `GET /api/v1/cold-start/cards`
取 18 张冷启动卡片（6 类 × 3 张，每类展示档 1 + 档 2-or-3 随机 + 档 4）。

响应：
```json
{
  "cards": [
    {
      "category": "pace",
      "category_label": "节奏",
      "options": [
        {"tag_id": 1, "name": "慢炖沉浸", "tier": 1,
         "tagline": "像在咖啡馆读一下午",
         "examples": ["《小森林》", "《海街日记》"]},
        {"tag_id": 2, "name": "张弛有度", "tier": 2, "...": "..."},
        {"tag_id": 4, "name": "爆裂快切", "tier": 4, "...": "..."}
      ]
    }
  ]
}
```

#### 4.2.2 `POST /api/v1/cold-start/submit`
提交冷启动选择。

请求：
```json
{"selected_tag_ids": [1, 6, 9, 14, 17, 22]}
```

校验：必须 6 个，且 6 大类恰好各 1 个。否则 400 `COLD_START_INVALID_SELECTION`。

副作用：
- 首次调用初始化 24 条 `user_vibe_relations`（全 0）
- 6 个选中 tag 的 `core_weight = +15`
- 写 6 条 `action_log`（`action='cold_start'`）
- 重复提交返回 `{"already_initialized": true}`，不再修改数据

响应：
```json
{"status": "ok", "profile_initialized": true, "radar_data": [...]}
```

#### 4.2.3 `POST /api/v1/vibe/analyze`
划词鉴定，核心接口。

请求：
```json
{
  "text": "赛博朋克2077的夜之城霓虹燃烧但灵魂冰冷",
  "domain": "game",
  "context": {"page_title": "...", "page_url": "..."}
}
```

处理流程（`llm_tagger.py`）：
1. `text_hash = sha256(trim(text) + domain)`
2. 查 `analysis_cache` WHERE `text_hash=? AND created_at > now()-7d`
3. 命中 → 取缓存 `tags_json` + `summary`，`hit_count += 1`
4. 未命中 → 调 LLM → 解析 JSON → 写缓存
5. `profile_calc.compute_match_score(user_id, tags)`
6. 对每个命中 tag：`curiosity_weight += 0.5`，写 `action_log`（`action='analyze'`）

响应：
```json
{
  "match_score": 73,
  "summary": "冷酷的机械美学配上一颗文艺的心——这正是你的菜。",
  "matched_tags": [
    {"tag_id": 11, "name": "赛博机械", "weight": 0.9},
    {"tag_id": 8, "name": "黑暗压抑", "weight": 0.7}
  ],
  "text_hash": "abc123...",
  "cache_hit": false
}
```

#### 4.2.4 `POST /api/v1/vibe/action`
态度确权。

请求：
```json
{
  "action": "star",
  "matched_tag_ids": [11, 8],
  "text_hash": "abc123..."
}
```

副作用：
- `star`：每个 tag `core_weight += 10`
- `bomb`：每个 tag `core_weight -= 10`
- 写 N 条 `action_log`

响应：
```json
{"status": "ok", "updated_tags": 2}
```

#### 4.2.5 `GET /api/v1/profile/radar`
Popup 雷达图数据。

响应：
```json
{
  "user_id": 1,
  "dimensions": [
    {
      "category": "pace",
      "category_label": "节奏",
      "score": 42.5,
      "dominant_tag": {"tag_id": 1, "name": "慢炖沉浸"}
    }
  ],
  "total_analyze_count": 37,
  "total_action_count": 8
}
```

### 4.3 LLM Prompt 模板

放 `llm_tagger.py` 作为常量：

```
你是一个内容品味分析器。下面给你一段关于【{domain}】的文字描述，
请从固定的 24 个元标签里选出最匹配的 1-5 个标签，并给每个 0-1 的权重。
同时用一句话（不超过 30 字）描述这段内容的核心 Vibe。

【标签池】（严格只能从这里选）：
{tag_pool_json}  // id + name + description + category

【待分析文字】：
{text}

输出严格 JSON：{"tags": [{"tag_id": 11, "weight": 0.9}, ...], "summary": "..."}
不要输出任何解释。
```

LLM 返回的 tag_id 不在 1-24 范围内 → 丢弃该条；全部被丢弃 → 等同 `LLM_PARSE_FAIL`。

### 4.4 关键服务实现要点

**`llm_tagger.py`**
- 支持 provider 切换（env `LLM_PROVIDER=claude|deepseek|openai`）
- `httpx.AsyncClient` 超时 10s
- 失败不重试（避免放大费用）
- 失败时不写缓存（避免错误结果被固化 7 天）

**`profile_calc.py`**
- `compute_match_score` 用 numpy cosine similarity，24 维向量
- `apply_curiosity_delta` 和 `apply_core_delta` 都走同一个内部 `_update_weight`，强制写 `action_log`
- V1.0 权重不做 clip

**`seed.py`**
- 脚本入口 `python -m app.services.seed`
- 幂等：`vibe_tags` 已有 24 条则跳过
- 同时 seed 冷启动卡片的 `tagline` 和 `examples`（Python dict 写死在代码里）

---

## 5. Chrome 插件架构

### 5.1 目录结构

```
extension/
├── manifest.json
├── src/
│   ├── background/
│   │   └── index.ts          # Service Worker：API Gateway + 消息路由
│   ├── content/
│   │   ├── index.ts          # 入口：监听选区、判断域、注入 Shadow Host
│   │   ├── domain.ts         # URL → domain 映射
│   │   ├── ui/
│   │   │   ├── FloatingIcon.ts
│   │   │   ├── VibeCard.ts
│   │   │   └── styles.css    # 构建时 inline 成字符串
│   │   └── messaging.ts      # 封装 chrome.runtime.sendMessage
│   ├── popup/
│   │   ├── popup.html
│   │   ├── popup.ts
│   │   ├── coldStart.ts
│   │   ├── radar.ts          # ECharts 雷达图
│   │   └── popup.css
│   ├── shared/
│   │   ├── types.ts          # 与后端 schemas 对齐的 TS 类型
│   │   ├── api.ts            # send<T>() 封装
│   │   └── constants.ts      # domain 白名单、阈值
│   └── assets/
│       └── icon.svg
├── build/                    # esbuild 产物
├── build.mjs
├── tsconfig.json
└── package.json
```

### 5.2 `manifest.json`（Manifest V3）

```json
{
  "manifest_version": 3,
  "name": "Vibe-Radar",
  "version": "1.0.0",
  "description": "潜意识审美鉴定器",
  "permissions": ["storage", "activeTab"],
  "host_permissions": [
    "http://localhost:8000/*",
    "https://book.douban.com/*",
    "https://movie.douban.com/*",
    "https://store.steampowered.com/*",
    "https://music.163.com/*"
  ],
  "background": { "service_worker": "build/background.js" },
  "content_scripts": [{
    "matches": [
      "https://book.douban.com/*",
      "https://movie.douban.com/*",
      "https://store.steampowered.com/*",
      "https://music.163.com/*"
    ],
    "js": ["build/content.js"],
    "run_at": "document_idle"
  }],
  "action": {
    "default_popup": "build/popup/popup.html",
    "default_icon": "src/assets/icon.svg"
  }
}
```

### 5.3 消息协议

```typescript
// shared/types.ts
type Domain = "book" | "game" | "movie" | "music";

type Msg =
  | { type: "ANALYZE";            payload: { text: string; domain: Domain; pageTitle: string; pageUrl: string } }
  | { type: "ACTION";             payload: { action: "star"|"bomb"; matchedTagIds: number[]; textHash?: string } }
  | { type: "COLD_START_GET_CARDS" }
  | { type: "COLD_START_SUBMIT";  payload: { selectedTagIds: number[] } }
  | { type: "GET_RADAR" };

type MsgResponse<T> = { ok: true; data: T } | { ok: false; error: { code: string; message: string } };
```

Background 侧一个总路由：

```typescript
chrome.runtime.onMessage.addListener((msg: Msg, _sender, sendResponse) => {
  (async () => {
    try {
      const data = await routeApi(msg);
      sendResponse({ ok: true, data });
    } catch (e) {
      sendResponse({ ok: false, error: serializeError(e) });
    }
  })();
  return true;
});
```

Content / Popup 侧统一封装：

```typescript
export function send<T>(msg: Msg): Promise<T> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(msg, (resp: MsgResponse<T>) => {
      if (resp.ok) resolve(resp.data);
      else reject(new Error(`${resp.error.code}: ${resp.error.message}`));
    });
  });
}
```

### 5.4 Content Script 核心逻辑

**Shadow DOM 注入**：
```typescript
let shadowHost: HTMLElement | null = null;
function ensureShadowHost() {
  if (shadowHost) return shadowHost;
  shadowHost = document.createElement("div");
  shadowHost.id = "vibe-radar-host";
  shadowHost.style.cssText = "position:absolute;top:0;left:0;z-index:2147483647;";
  const shadow = shadowHost.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent = INLINE_CSS;  // esbuild 构建时 inline
  shadow.appendChild(style);
  document.body.appendChild(shadowHost);
  return shadowHost;
}
```

**选区监听**：
```typescript
document.addEventListener("mouseup", () => {
  const sel = window.getSelection();
  const text = sel?.toString().trim() ?? "";
  if (text.length < 2 || text.length > 200) return hideFloatingIcon();

  const domain = detectDomain(location.href);
  if (!domain) return;

  const rect = sel!.getRangeAt(0).getBoundingClientRect();
  showFloatingIcon({
    x: rect.right + window.scrollX,
    y: rect.top + window.scrollY - 8,
    text,
    domain
  });
});
```

**两个 UI 组件（Shadow DOM 内）**：
- `FloatingIcon`：圆形小图标，绝对定位在选区右上角。点击 → 调 `ANALYZE` → 拿结果 → 原地向下展开 `VibeCard`
- `VibeCard`：展示匹配度百分比（圆环动画）、AI 侧写、命中的 tags、底部 💎/💣 按钮
  - 💎 点击 → 调 `ACTION`(star) → 按钮变亮 + 撒花动画（纯 CSS）
  - 💣 点击 → 调 `ACTION`(bomb) → 按钮变亮 + 抖动动画
  - 鼠标移出 1500ms / 滚动 / ESC → 卡片消失

**域识别**：
```typescript
const DOMAIN_RULES: Array<{ test: RegExp; domain: Domain }> = [
  { test: /^https?:\/\/book\.douban\.com\//,      domain: "book" },
  { test: /^https?:\/\/movie\.douban\.com\//,     domain: "movie" },
  { test: /^https?:\/\/store\.steampowered\.com\//, domain: "game" },
  { test: /^https?:\/\/music\.163\.com\//,        domain: "music" },
];
export function detectDomain(url: string) {
  return DOMAIN_RULES.find(r => r.test.test(url))?.domain ?? null;
}
```

V1.0 不做兜底手选——白名单外 content script 根本不注入。

### 5.5 Popup 页面

三个状态由 `chrome.storage.local.profile_initialized` 标志位决定：

1. 未初始化 → 渲染 `coldStart.ts`（18 张卡片，6 行 × 3 列）
2. 已初始化 → 渲染 `radar.ts`（ECharts 雷达图 + 统计）
3. 加载中 / 错误 → loading / error toast

冷启动交互：
- 每一行代表一个 category，必须选一张
- 6 行全部选完后底部"开始鉴定"按钮亮起
- 提交成功写 `chrome.storage.local.profile_initialized = true`，切到雷达图

雷达图：
- ECharts 仅在 popup bundle 里（`build/popup/echarts.min.js`）
- 每次打开 popup 拉一次数据，不做实时推送

### 5.6 构建

`build.mjs` 要点：
- esbuild 分别打包 `background.ts`、`content.ts`、`popup.ts` 三个入口
- `content.ts` 打包时用 text 插件把 `styles.css` inline 成 `INLINE_CSS` 字符串
- `popup.html` 的 `<script>` 引本地 `popup.js`（不能用 inline script，违反 MV3 CSP）
- 支持 `watch` 模式

---

## 6. 核心流程时序

### 6.1 冷启动

```
Popup 打开
  └→ 读 chrome.storage.local.profile_initialized
      ├─ false → send(COLD_START_GET_CARDS)
      │           └→ background → GET /cold-start/cards
      │           ← 渲染 18 张卡片
      │   用户选完 6 张点"开始鉴定"
      │   └→ send(COLD_START_SUBMIT, {selectedTagIds})
      │       └→ background → POST /cold-start/submit
      │                       ├→ 校验 6 个 + 覆盖 6 类
      │                       ├→ 初始化 24 条 user_vibe_relations
      │                       ├→ 6 个 core_weight = +15
      │                       └→ 写 6 条 action_log
      │       ← {status, radar_data}
      │   写 chrome.storage.local.profile_initialized = true
      │   切到雷达图视图
      └─ true  → send(GET_RADAR) → 渲染雷达图
```

### 6.2 划词鉴定

```
用户选中"赛博朋克的世界观但有治愈的灵魂"
  └→ content.ts mouseup
      ├→ 校验长度 2-200、白名单命中
      ├→ detectDomain() = "book"
      └→ 显示 FloatingIcon 在选区右上角
          用户点击
          └→ send(ANALYZE, {text, domain, pageTitle, pageUrl})
              └→ background → POST /vibe/analyze
                  ├→ llm_tagger: hash 查 analysis_cache
                  │   ├─ 命中 → 取缓存
                  │   └─ 未命中 → 调 LLM → 解析 → 写缓存
                  ├→ profile_calc.compute_match_score
                  └→ 对每个命中 tag：curiosity += 0.5 + action_log
              ← {match_score, summary, matched_tags, text_hash}
          FloatingIcon 下方展开 VibeCard
```

### 6.3 态度确权

```
VibeCard 点击 💎
  └→ send(ACTION, {action:"star", matchedTagIds, textHash})
      └→ background → POST /vibe/action
          ├→ 每个 tag core_weight += 10
          └→ 写 N 条 action_log
      ← {status:"ok"}
  💎 按钮变亮 + 撒花动画
  1.5s 后 VibeCard 淡出
```

---

## 7. 错误处理矩阵

| 场景 | 位置 | 处理 |
|---|---|---|
| 后端未启动（fetch 失败） | background | 返回 `BACKEND_DOWN`，UI 显示"后端未运行，请先启动 FastAPI" |
| LLM 超时（>10s） | llm_tagger | 503 `LLM_TIMEOUT`，UI 显示"鉴定超时，请重试"，**不写缓存** |
| LLM 返回 JSON 解析失败 | llm_tagger | 503 `LLM_PARSE_FAIL`，**不写缓存** |
| LLM 返回 tag_id 越界 | llm_tagger | 丢弃该条；全部丢弃则等同 `LLM_PARSE_FAIL` |
| 冷启动 6 个 tag 不覆盖 6 类 | router | 400 `COLD_START_INVALID_SELECTION` |
| 重复提交冷启动 | router | 200 `{already_initialized:true}`，前端跳雷达图 |
| 选区长度 <2 或 >200 | content | 静默不激活 |
| 选区跨 iframe | content | V1.0 不支持，静默不激活 |
| 用户在加载时切页 | content | 组件卸载时忽略返回 |
| SQLite 并发写入冲突 | SQLAlchemy | V1.0 单用户单进程，不处理 |

---

## 8. 测试策略

### 8.1 后端（pytest）

- `test_cold_start.py`：初始化 24 条关系、6 个 +15、校验错误 case、幂等
- `test_analyze.py`：缓存命中/未命中、LLM mock 返回、JSON 解析失败不写缓存、匹配度边界
- `test_action.py`：star/bomb 的 ±10 增量、action_log 审计
- `test_profile_calc.py`：cosine similarity + 归一化（纯函数，最好覆盖）
- 覆盖目标：services ≥85%，routers ≥70%

LLM 测试用 `FakeLlmTagger` 注入固定返回值，不打真 API。真 API 仅在 `test_integration.py` 里，标记 `@pytest.mark.integration`，默认不跑。

### 8.2 前端

V1.0 不做自动化测试。手动冒烟清单放 `extension/SMOKE.md`：

1. 装插件 → Popup → 看到 18 卡片 → 选 6 张 → 看到雷达图
2. 豆瓣书评页划词 2-10 字 → icon 出现 → 点击 → 卡片出现 → 匹配度显示
3. 💎 点击 → 动画 + 卡片消失
4. 再次划同一段文字 → 应命中缓存（background 日志 `cache_hit:true`）
5. 关掉 FastAPI → 划词 → 卡片显示"后端未运行"

---

## 9. 交付与启动

### 9.1 仓库结构

```
vibe4.0/
├── backend/
├── extension/
├── docs/
│   └── superpowers/specs/2026-04-14-vibe-radar-v1-design.md
└── README.md
```

### 9.2 启动顺序（开发期）

```bash
# 1. 启动后端
cd backend && python -m venv .venv && . .venv/Scripts/activate
pip install -r requirements.txt
python -m app.services.seed        # 首次灌种子数据
uvicorn app.main:app --reload --port 8000

# 2. 构建插件
cd extension && npm install && npm run build

# 3. Chrome → 扩展 → 开发者模式 → 加载已解压的扩展 → 选 extension/build/
```

### 9.3 环境变量（`backend/.env`）

```
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-...
LLM_MODEL=deepseek-chat
DB_PATH=./data/vibe_radar.db
```

---

## 10. Non-Goals（V1.0 明确不做）

- 精选池推荐（方案 β 第二阶段）
- 用户注册 / 登录 / JWT
- 云端部署 / 跨设备同步
- 画像回滚 / 撤销确权
- 兜底手选域识别
- 前端自动化测试
- 多用户并发

这些留给 V1.1+ 版本。
