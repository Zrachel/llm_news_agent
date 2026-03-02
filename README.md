# LLM News Agent

实时监控 LLM（大语言模型）研究进展的 Agent，自动推送相关论文和新闻到 Telegram。

## 功能特性

- **多源监控**
  - 📚 arXiv: 监控 cs.CL、cs.LG 分类的最新论文
  - 🐦 X.com: 通过 Nitter RSS 监控 AI 领域关键账号
  - 📕 小红书: 可选，监控 AI/LLM 相关内容

- **智能过滤**: 使用 LLM (GPT-4o-mini/GLM-4) 自动识别与「纯文本 LLM」相关的内容
- **实时推送**: 通过 Telegram Bot 即时推送相关更新
- **重要性评级**: 自动评估内容重要程度（🔥🔥🔥 / 🔥🔥 / 🔥）

## 快速开始

### 1. 安装依赖

```bash
cd llm-news-agent
pip install -e .
```

### 2. 配置

复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的配置：

```bash
# OpenAI API（用于 LLM 过滤）
OPENAI_API_KEY=sk-your-api-key

# Telegram Bot
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
TELEGRAM_CHAT_ID=your-chat-id

# 可选：小红书 Cookie
# XIAOHONGSHU_COOKIE=your-cookie
```

### 3. 获取 Telegram 配置

1. 在 Telegram 搜索 `@BotFather`
2. 发送 `/newbot`，按提示创建 Bot
3. 记录返回的 Token
4. 搜索 `@userinfobot`，发送任意消息获取你的 Chat ID

### 4. 运行

```bash
python -m src.main
```

或使用后台运行：

```bash
# 使用 screen
screen -S llm-agent
python -m src.main

# 或使用 nohup
nohup python -m src.main > agent.log 2>&1 &
```

## 配置说明

编辑 `config/settings.yaml` 可自定义：

- 监控间隔时间
- arXiv 搜索关键词和分类
- X.com 监控账号列表
- 小红书搜索关键词
- LLM 过滤模型和参数

## 项目结构

```
llm-news-agent/
├── CLAUDE.md           # Claude Code 项目上下文
├── README.md           # 本文件
├── pyproject.toml      # 项目依赖
├── config/
│   └── settings.yaml   # 配置文件
├── src/
│   ├── main.py         # 入口
│   ├── agent.py        # 主 Agent
│   ├── monitors/       # 数据源监控
│   ├── filters/        # LLM 过滤
│   └── notifiers/      # 推送通知
└── tests/              # 测试
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/ -v

# 类型检查
mypy src/

# 代码检查
ruff check src/
```

## 常见问题

### Nitter 实例不可用

Nitter 实例可能会下线。如果 X.com 监控失败，可以：
1. 检查 `config/settings.yaml` 中的 Nitter 实例列表
2. 访问 [Nitter 实例列表](https://github.com/zedeus/nitter/wiki/Instances) 获取可用实例
3. 更新配置文件

### 小红书 Cookie 过期

小红书 Cookie 会定期过期，需要重新获取：
1. 浏览器登录 xiaohongshu.com
2. F12 → Network → 刷新页面
3. 找到任意请求，复制 Cookie 字段
4. 更新 `.env` 文件

## License

MIT
