# 「论文到公众号」全自动流水线

> AI论文学习 → 解读文章 → 审稿 → 发布 → 数据回收 → 反哺撰文的完整闭环

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Paper → WeChat Pipeline 是一套全自动的学术论文到微信公众号文章的处理流水线。它能够自动获取最新 AI 论文、生成解读文章、通过多轮审稿保证质量、一键发布到微信公众号草稿箱，并持续收集阅读数据以反哺后续的撰写策略。

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        Paper → WeChat Pipeline (7-Step)                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐               │
│   │ ① Learn  │───▶│ ② Write  │───▶│ ③ Review │───▶│④ Publish │               │
│   │ 论文获取  │    │ AI 撰文   │    │ 多轮审稿  │    │ 公众号发布 │               │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘               │
│         ▲                                               │                    │
│         │                                               ▼                    │
│   ┌──────────┐    ┌──────────┐                   ┌──────────┐               │
│   │⑦ Strategy│◀───│⑥ Profile │◀──────────────────│⑤Analytics│               │
│   │ 策略反哺  │    │ 用户画像  │                   │ 数据回收  │               │
│   └──────────┘    └──────────┘                   └──────────┘               │
│         │              │                              │                      │
│         └──────────────┴──────────────────────────────┘                      │
│                        ▼                                                     │
│               ┌───────────────┐                                              │
│               │  Browser Ops  │  ← 浏览器自动化层（全局支撑）                   │
│               │  浏览器操作    │                                              │
│               └───────────────┘                                              │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 流水线七步详解

| 步骤 | 模块 | 职责 |
|------|------|------|
| ① Learn | `learn` | 自动抓取 arXiv、顶会最新论文，提取关键信息并入库 |
| ② Write | `write` | 基于论文摘要和全文，由 LLM 生成通俗易懂的解读文章 |
| ③ Review | `review` | 多轮 AI 审稿：事实核查、可读性评分、标题优化 |
| ④ Publish | `publish` | 通过微信公众号 API 将文章推送到草稿箱，支持定时发布 |
| ⑤ Analytics | `analytics` | 定时采集阅读量、在看、分享等微信后台数据 |
| ⑥ Profile | `profile` | 基于历史阅读数据构建用户兴趣画像 |
| ⑦ Strategy | `strategy` | 根据画像和热点趋势，推荐下周选题和写作策略 |

### 支撑层

| 模块 | 职责 |
|------|------|
| `browser` | 浏览器自动化层，处理需要登录态或 JS 渲染的场景（如微信公众号后台数据抓取） |

---

## 快速开始

### 环境要求

- Python 3.10+
- pip

### 安装

```bash
git clone https://github.com/your-org/paper-to-wechat-pipeline.git
cd paper-to-wechat-pipeline
make install
```

### 配置

在 `~/.paper-to-wechat/config.json` 中配置你的微信公众号凭证：

```json
{
  "wechat_appid": "your_appid",
  "wechat_appsecret": "your_appsecret",
  "data_dir": "~/paper-to-wechat-data",
  "collector_port": 8899
}
```

也可以通过环境变量设置（优先级低于配置文件）：

- `WECHAT_APPID`
- `WECHAT_APPSECRET`
- `PAPER_TO_WECHAT_DATA_DIR`
- `PAPER_TO_WECHAT_COLLECTOR_PORT`

### 运行

```bash
# 启动数据采集服务（后台常驻）
make collector-start

# 生成用户画像报告
make profile

# 生成每周选题策略
make strategy

# 发布单篇文章到微信公众号草稿箱
make publish FILE=output/article_2025.md

# 审稿某篇文章
python -m pipeline run review --file output/article_2025.md

# 停止数据采集服务
make collector-stop

# 清理临时文件
make clean
```

### 运行测试

```bash
make test
```

---

## 项目结构

```
paper-to-wechat-pipeline/
├── pipeline/               # 核心流水线包
│   ├── __init__.py         # 版本号
│   ├── config.py           # 统一配置管理
│   └── run.py              # CLI 入口
├── modules/                # 功能模块
│   ├── learn/              # 论文获取与学习
│   ├── write/              # AI 文章撰写
│   ├── review/             # 自动审稿
│   ├── publish/            # 微信公众号发布
│   ├── analytics/          # 数据采集与分析
│   └── browser/            # 浏览器自动化
├── tests/                  # 测试
├── Makefile                # 常用命令快捷入口
├── LICENSE
└── README.md
```

---

## 配置详解

配置文件位于 `~/.paper-to-wechat/config.json`，支持以下字段：

| 键 | 类型 | 必填 | 说明 | 环境变量 |
|---|------|------|------|----------|
| `wechat_appid` | string | 是 | 微信公众号 AppID | `WECHAT_APPID` |
| `wechat_appsecret` | string | 是 | 微信公众号 AppSecret | `WECHAT_APPSECRET` |
| `data_dir` | string | 否 | 数据存储目录，默认 `~/paper-to-wechat-data` | `PAPER_TO_WECHAT_DATA_DIR` |
| `collector_port` | int | 否 | 采集器 HTTP 服务端口，默认 8899 | `PAPER_TO_WECHAT_COLLECTOR_PORT` |

---

## License

MIT License. 详见 [LICENSE](LICENSE) 文件。
