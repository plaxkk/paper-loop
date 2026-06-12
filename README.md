# 🔄 Paper Loop —— 论文驱动的全自动内容飞轮

> **一篇论文进去，四平台文章出来。数据跑回来，策略再反哺。**
>
> AI 论文学习 → 多平台文章生成 → 自动审稿 → 一键分发（公众号/知乎/掘金/CSDN）→ 阅读数据回收 → 策略复盘 —— 一个工程师用 AI 理解 AI 的完整工具链。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

---

## 为什么你需要 Paper Loop？

市面上不缺「论文摘要工具」，也不缺「公众号排版工具」。但它们各自只做了一件事，你得自己把它们串起来。

**Paper Loop 做的是「完整闭环」**：从你读完一篇论文到你四个平台的文章发出、再到一周后回来看数据调整方向——这一整条链路上所有机械的、重复的、可以自动化的环节，全部交给它。

写一篇深度解读文章需要 3-4 小时。Paper Loop 把这变成 30 分钟的审阅 + 一键发布。

---

## 架构

```
                    ┌─────────────────┐
                    │   ① Learn       │  arXiv / 论文原文
                    │   论文学习       │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   ② Write       │  LLM 撰稿（HTML）
                    │   AI 撰文       │  LaTeX 公式 / 论文原图
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   ③ Review      │  AI 审稿（事实核查）
                    │   自动审稿       │  可读性 / 标题优化
                    └────────┬────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
   ┌──────────┐      ┌──────────┐      ┌──────────┐
   │ 公众号    │      │  知乎    │      │ 掘金/CSDN │
   │ 草稿箱    │      │  草稿     │      │  草稿     │
   └──────────┘      └──────────┘      └──────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ ⑤ Analytics     │  阅读量 / 在看 / 分享
                    │   数据回收       │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ ⑥ Profile       │  用户兴趣画像
                    │  + ⑦ Strategy   │  选题策略复盘
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  下一篇文章      │  数据反哺撰文
                    └─────────────────┘
```

---

## 核心能力

| 模块 | 做了什么 | 为什么重要 |
|------|---------|-----------|
| **论文解读撰写** | LLM 将论文转为公众号风格 HTML，含 LaTeX 公式渲染、论文原图提取 | 不是机翻摘要，是有观点、有工程类比的深度文章 |
| **多平台适配** | HTML → 知乎/掘金/CSDN Markdown，自动处理格式差异 | 一稿多发，不用手动改排版 |
| **自动审稿** | LLM 对比论文原文逐句核查事实，分级报告 error/warning/suggestion | 发布前最后一道防线 |
| **一键分发** | 通过 wechatsync 同步到公众号/知乎/掘金/CSDN（草稿模式） | 4 平台共 30 秒 |
| **数据飞轮** | 定时采集阅读数据 → 用户画像 → 周策略复盘 | 不是拍脑袋选题，数据说话 |
| **公式渲染** | CodeCogs SVG → PNG → 微信 CDN，支持块级 + 行内 LaTeX | 微信原生不支持 MathJax，这条路是唯一解 |
| **论文原图提取** | PDF 精准裁剪（基于 caption 定位），矢量图 8x 超采样渲染 | 文章里的图不是截图，是论文原图 |

---

## 横向对比

| 项目 | Stars | 做论文解读 | 多平台发布 | 数据回收 | 完整闭环 |
|------|-------|:---:|:---:|:---:|:---:|
| **Paper Loop** 🆕 | — | ✅ | ✅ 4平台 | ✅ | ✅ |
| [wechatsync/Wechatsync](https://github.com/wechatsync/Wechatsync) | 5.7k | ❌ | ✅ 29平台 | ❌ | ❌ |
| [geekjourneyx/md2wechat-skill](https://github.com/geekjourneyx/md2wechat-skill) | 2.8k | ❌ | ⚠️ 仅公众号 | ❌ | ❌ |
| [zhangleino1/paper-summarizer](https://github.com/zhangleino1/paper-summarizer) | 126 | ✅ | ❌ | ❌ | ❌ |
| [xiuqiang1995/wechat-ai-publisher](https://github.com/xiuqiang1995/wechat-ai-publisher) | 7 | ❌ | ✅ 仅公众号 | ❌ | ❌ |

**Paper Loop 是唯一一个同时覆盖「论文 → 多平台 → 数据回收 → 策略反哺」全链路的工具。**

> wechatsync 是 Paper Loop 的分发引擎——我们把它接入了完整的内容飞轮。

---

## 快速开始

### 环境

- Python 3.10+
- Node.js（wechatsync CLI）
- Chrome + [文章同步助手](https://chromewebstore.google.com/detail/文章同步助手/hchobocdmclopcbnibdnoafilagadion) 扩展（多平台分发需要）

### 安装

```bash
git clone https://github.com/plaxkk/paper-loop.git
cd paper-loop
pip install -r requirements.txt
npm install -g @wechatsync/cli
```

### 分发一篇已有的文章

```bash
# 生成多平台适配版本
python -m pipeline.run distribute-adapt data/articles/your_article.json

# 干跑预览（不实际发布）
python -m pipeline.run distribute-publish data/articles/your_article.json --dry-run

# 正式发布到四个平台草稿箱
python -m pipeline.run distribute-publish data/articles/your_article.json
```

### 更多命令

```bash
python -m pipeline.run review <file>           # 审稿
python -m pipeline.run render-formula <file>   # 公式渲染
python -m pipeline.run extract-figures P14     # 提取论文原图
python -m pipeline.run publish <file>          # 发布到公众号草稿箱
python -m pipeline.run profile                 # 用户画像报告
python -m pipeline.run strategy                # 周策略复盘
```

---

## 项目结构

```
paper-loop/
├── pipeline/              # 核心流水线
│   └── run.py             # CLI 入口
├── modules/
│   ├── write/             # AI 撰文 + 公式渲染 + 论文图提取
│   ├── review/            # LLM 审稿（对比论文原文）
│   ├── publish/           # 公众号 API 发布
│   ├── distribution/      # 多平台分发（wechatsync 编排 + HTML→MD 适配）
│   ├── analytics/         # 数据采集 + 用户画像 + 策略生成
│   └── browser/           # 浏览器自动化层
├── skills/                # Hermes Agent 技能文件
├── data/                  # 文章 JSON、分布式输出、报告
├── Makefile
├── LICENSE
└── README.md
```

---

## 安全

- Token 和密钥仅存放在 `~/.hermes/.env`（不在仓库内）
- `.env` 和生成文件已加入 `.gitignore`
- 分发通过 Chrome 扩展本地完成，不经过第三方服务器

---

## License

MIT License. 详见 [LICENSE](LICENSE) 文件。
