<p align="center">
  <strong style="font-size:32px">✦ Vibe-Radar</strong>
  <br/>
  <em>划词即鉴 · 你的审美雷达</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" />
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi" />
  <img src="https://img.shields.io/badge/Chrome-MV3-4285F4?logo=googlechrome" />
  <img src="https://img.shields.io/badge/LLM-DeepSeek%20|%20GPT%20|%20Claude-ff6b6b" />
  <img src="https://img.shields.io/badge/License-MIT-green" />
</p>

---

**Vibe-Radar** 是一个基于 LLM 的个性化内容匹配工具。在任何网页上选中一段文字（电影名、书名、游戏名），它会告诉你：**这东西适不适合你**。

不是冷冰冰的评分，而是像一个懂你审美的朋友，用人话告诉你值不值得花时间。

## Demo

```
你划了"三体" →

  85%  追

  这书简直为你量身打造——你平时就爱琢磨那些宏大叙事和硬核科幻，
  刘慈欣的宇宙观够你消化好几个月。不过以你的脾气，前半段可能嫌慢，
  坚持到第二部就停不下来了。值得追，85%。
```

## 核心特色

- **划词即鉴** — 选中文字，点击图标，秒出分析
- **联网搜索** — 自动搜索作品信息，不怕 LLM 训练数据过时
- **个性化匹配** — 基于 MBTI + 24 维审美标签 + 行为学习，越用越准
- **朋友语气** — 不是 AI 味的"综上所述"，是朋友式的直接点评
- **SSE 流式输出** — 分数先出，点评打字机效果，不干等
- **多模型支持** — DeepSeek / GPT / Claude / Kimi / Qwen / GLM，自由切换
- **暗色/亮色主题** — 赛博朋克风格，一键切换

## 架构

```
Chrome Extension (MV3)
  ├── Content Script (Shadow DOM)  ← 划词检测 + 浮窗 UI
  ├── Background Worker            ← SSE 流式转发
  └── Popup                        ← 雷达图 + 设置

FastAPI Backend
  ├── Agent 1: 识别官 (llm_identifier)
  │   ├── DuckDuckGo 联网搜索
  │   ├── 标题补全 + 域名强制校验
  │   └── 7 天缓存 (analysis_cache)
  ├── Judge: 匹配官+朋友 (llm_judge)
  │   ├── cosine base_score ± LLM adjustment (±15)
  │   ├── 3 条理由 + verdict (追/看心情/跳过)
  │   └── 60-120 字朋友语气点评
  ├── 24 维标签体系 (6类×4层)
  │   └── cosine similarity 匹配
  ├── 用户画像
  │   ├── MBTI 冷启动种子
  │   ├── core_weight + curiosity_weight
  │   └── 后台反馈分析 (每5分钟)
  └── SQLite (零配置)
```

## 快速开始

### 一键启动

```bash
git clone https://github.com/YOUR_USERNAME/vibe-radar.git
cd vibe-radar

# Windows: 双击 start.bat
# Mac/Linux: ./start.sh
```

首次运行会自动创建虚拟环境、安装依赖、初始化数据库。

如果没有 `.env` 文件，会自动从模板创建并提示你填入 API Key。

### 手动启动

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate  # Windows
# source .venv/bin/activate    # Mac/Linux

pip install -r requirements.txt
cp .env.example .env           # 编辑 .env 填入 API Key
python -m app.services.seed    # 初始化数据库
uvicorn app.main:app --port 8000
```

### 配置大模型

**方式 1：Web 界面**（推荐）

打开 `http://localhost:8000` → 设置 → 选厂商 → 填 Key → 测试连接 → 保存

**方式 2：`.env` 文件**

```env
LLM_API_KEY=sk-your-key-here
```

### 安装 Chrome 扩展（划词功能）

```bash
cd extension
npm install && npm run build
```

Chrome → `chrome://extensions` → 开发者模式 → 加载已解压 → 选 `extension/build`

### 开始使用

- **Web 版**：打开 `http://localhost:8000`，粘贴文字鉴定
- **插件版**：任意网页选中文字 → 点紫色 ✦ 图标

## 支持的模型

| 厂商 | 模型 | 特点 |
|------|------|------|
| DeepSeek | deepseek-chat | 性价比最高 |
| OpenAI | gpt-4o, gpt-4o-mini | 效果最好 |
| Anthropic | claude-sonnet-4-20250514 | 中文理解强 |
| Moonshot | moonshot-v1-8k | 国内快 |
| 通义千问 | qwen-plus, qwen-turbo | 免费额度多 |
| 智谱 | glm-4-flash | 免费 |
| 自定义 | 任意 OpenAI 兼容接口 | — |

## 24 维审美标签

6 个维度，每个 4 层：

| 维度 | 标签 |
|------|------|
| **节奏** | 慢炖沉浸 → 轻快明快 → 紧凑高压 → 碎片跳切 |
| **情绪** | 治愈温暖 → 黑暗压抑 → 热血燃烧 → 荒诞讽刺 |
| **认知** | 轻度消遣 → 烧脑解谜 → 认知挑战 → 哲学思辨 |
| **叙事** | 线性叙事 → 多线交织 → 非线性碎片 → 元叙事 |
| **世界观** | 日常写实 → 奇幻架空 → 赛博机械 → 宇宙史诗 |
| **强度** | 佛系躺平 → 中度刺激 → 高强度 → 极限施压 |

## 匹配算法

```
final_score = clamp(cosine_base_score + llm_adjustment, 0, 100)
```

1. **cosine_base_score** — 用户 24 维向量 vs 作品 24 维向量的余弦相似度
2. **llm_adjustment** — LLM 基于性格分析的微调（±15 分）
3. **verdict** — 追 / 看心情 / 跳过

用户画像来源：
- MBTI 冷启动种子权重
- 每次划词的 curiosity_weight（好奇心）
- 太准了吧/差点意思 的 core_weight（核心偏好）
- 后台 LLM 反馈分析（每 5 分钟）

## 项目结构

```
vibe-radar/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── config.py               # 环境变量
│   │   ├── models/                 # 数据模型
│   │   ├── services/
│   │   │   ├── llm_identifier.py   # 识别官（搜索+识别）
│   │   │   ├── llm_judge.py        # 匹配官+朋友（评分+点评）
│   │   │   ├── llm_recommender.py  # 同频代餐
│   │   │   ├── profile_calc.py     # 数学引擎
│   │   │   └── feedback_analyzer.py # 后台反馈
│   │   ├── routers/                # API 路由
│   │   └── static/index.html       # Web 版 UI
│   ├── tests/                      # 111 个测试
│   └── data/                       # SQLite
├── extension/
│   ├── manifest.json               # Chrome MV3
│   └── src/
│       ├── content/                # 划词 + 浮窗
│       ├── background/             # SSE 转发
│       └── popup/                  # 雷达图 + 设置
└── README.md
```

## 开发

```bash
# 运行测试
cd backend && source .venv/Scripts/activate
python -m pytest -v              # 111 tests

# 构建扩展
cd extension && npm run build
```

### 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.10+ / FastAPI / SQLAlchemy 2.x / SQLite |
| 前端 | TypeScript / esbuild / Chrome MV3 / Shadow DOM |
| LLM | OpenAI 兼容接口 |
| 搜索 | DuckDuckGo (ddgs) |
| 图表 | ECharts 5 |
| 测试 | pytest / httpx / asyncio |

## FAQ

**Q: API 费用大概多少？**
A: DeepSeek 约 ¥0.01-0.03/次，每天 20 次约 ¥0.3-0.6。

**Q: 支持哪些网站？**
A: 所有网站。内置 40+ 站点自动识别（豆瓣、IMDb、Steam、Netflix、B站等），其他网站 LLM 自动判断。

**Q: 数据存在哪？**
A: 本地 SQLite，不上传任何数据。

**Q: 如何重置？**
A: 删除 `backend/data/vibe_radar.db`，重新 `python -m app.services.seed`。

## Contributing

欢迎 PR 和 Issue！

## License

[MIT](LICENSE)
