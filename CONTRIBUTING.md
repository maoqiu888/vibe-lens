# Contributing to Vibe-Radar

感谢你有兴趣为 Vibe-Radar 贡献代码！

## 提交流程

1. **Fork** 本仓库
2. 创建分支：`git checkout -b feat/your-feature`
3. 提交代码：`git commit -m "feat: 描述你的改动"`
4. 推送：`git push origin feat/your-feature`
5. 发起 **Pull Request**

## 开发环境

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Windows
pip install -r requirements.txt
python -m app.services.seed

cd ../extension
npm install
npm run build
```

## 代码规范

- **后端**：Python 3.10+，遵循现有代码风格，函数加类型注解
- **前端**：TypeScript，esbuild 构建
- **提交信息**：使用 [Conventional Commits](https://www.conventionalcommits.org/)
  - `feat:` 新功能
  - `fix:` Bug 修复
  - `docs:` 文档
  - `perf:` 性能优化
  - `refactor:` 重构

## 测试

所有 PR 必须通过测试：

```bash
cd backend
python -m pytest -v   # 必须全部通过
```

新增功能请附带测试用例。

## 可以贡献什么

- 新的域名识别规则（`extension/src/shared/constants.ts`）
- LLM Prompt 优化（`backend/app/services/llm_*.py`）
- UI/UX 改进
- 新的 LLM 厂商支持（`backend/app/routers/settings.py` PROVIDERS）
- Bug 修复
- 文档翻译（英文 README）
- 性能优化

## 注意事项

- 不要提交 API Key 或任何密钥
- 不要提交 `backend/data/*.db` 数据库文件
- PR 描述清楚改了什么、为什么改

## 行为准则

尊重每一个参与者。保持友善和建设性。
