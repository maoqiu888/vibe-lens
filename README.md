<p align="center">
  <strong style="font-size:32px">✦ Vibe-Lens</strong>
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

**Vibe-Lens** 是一个基于 LLM 的个性化内容匹配工具。在任何网页上选中一段文字（电影名、书名、游戏名），它会告诉你：**这东西适不适合你**。

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
git clone https://github.com/maoqiu888/vibe-lens.git
cd vibe-lens

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
vibe-lens/
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

## Roadmap

### 近期计划

- [ ] Embedding 层替代部分 LLM 调用（bge-small 做标签预测，成本降低 100 倍）
- [ ] 域名白名单结构化解析（豆瓣/IMDb 直接抓结构化数据，跳过 LLM）
- [ ] 用户画像扩展：anti_tags（反感标签）、fatigue_tags（审美疲劳）
- [ ] 多语言支持（English UI + prompts）
- [ ] Firefox / Edge 扩展适配

### 未来畅想

**1. 审美社交网络**

> 你的审美雷达就是你的社交名片

每个用户有一张 24 维审美指纹。当两个人的雷达图高度重合，说明你们是"审美同频"的人。可以衍变为：
- **审美匹配**：找到和你品味最像的人，看看他们最近在看什么
- **审美圈子**：自动聚类形成"慢炖沉浸党"、"赛博机械控"等兴趣社群
- **审美简历**：求职/社交时展示你的审美雷达图，比 MBTI 更有信息量

**2. 内容推荐引擎**

> 不是"大家都在看"，而是"你一定会喜欢"

Vibe-Lens 的 24 维向量 + 用户反馈数据，天然是一个推荐系统的冷启动方案：
- 接入 Netflix / Steam / Kindle 的观看/游玩/阅读记录，自动构建审美画像
- 跨域推荐："你喜欢《三体》→ 你可能喜欢《群星》（游戏）→ 你可能喜欢 Radiohead（音乐）"
- 为内容平台提供 Vibe-based Recommendation API

**3. 创作者工具**

> 帮创作者理解：我的作品吸引的是什么样的人

- 作者/导演/游戏设计师上传作品 → 获得 24 维 Vibe 分析
- 对比目标受众画像 vs 作品画像，发现"你以为你在做治愈片，其实观众觉得是黑暗压抑"
- A/B 测试不同标题/封面/简介对 Vibe 感知的影响

**4. 情绪感知推荐**

> 不是"你一直喜欢什么"，而是"你现在需要什么"

- 深夜 + 独处 → 推荐治愈/陪伴感内容
- 周末下午 → 推荐沉浸式长内容
- 通勤碎片时间 → 推荐轻快/短内容
- 结合日历、天气、生物钟，做"此刻最适合你的一部作品"

**5. 学术研究方向**

本项目的技术框架为以下研究提供了实验平台：

- **计算美学 (Computational Aesthetics)**：审美偏好能否用有限维向量空间量化？24 维够不够？
- **冷启动问题**：MBTI → 审美画像的映射效果如何？性格测试能替代多少行为数据？
- **LLM 评估一致性**：LLM 的"审美判断"和人类评分的相关性有多高？不同模型差异多大？
- **跨文化审美**：中国用户 vs 欧美用户的 24 维分布有什么系统性差异？
- **审美漂移 (Taste Drift)**：用户的审美画像随时间如何变化？有没有"审美生命周期"？

## Community

本项目由 [LINUX DO](https://linux.do) 社区支持推广。

[![LINUX DO](https://img.shields.io/badge/LINUX%20DO-社区-blue?logo=discourse)](https://linux.do)

## Contributing

欢迎 PR 和 Issue！详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## License

[MIT](LICENSE)

---

<p align="center">
  如果觉得有意思，给个 Star 吧 ✦
</p>
