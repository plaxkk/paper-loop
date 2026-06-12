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
                         ┌──────────────────────────────────────┐
                         │          Paper Loop (7-Step)          │
                         └──────────────────────────────────────┘

  ┌──────────┐    ┌───────────────────────────────┐    ┌──────────┐
  │ ① Learn  │    │         ② Write ─ AI 撰文      │    │ ③ Review │
  │ 论文原文  │    │                               │    │ 自动审稿  │
  │ arXiv/   │───▶│  ┌─────────────────────────┐  │───▶│          │
  │ PDF/源码  │    │  │ 人设（用户可配置）        │  │    │ 事实核查  │
  └──────────┘    │  │ INTJ 风格 · 工程类比       │  │    │ 可读性    │
                  │  │ 禁止 AI 腔 · 具体判断       │  │    │ 标题优化  │
                  │  └─────────────────────────┘  │    │ 分级报告  │
                  │           │                    │    └────┬─────┘
                  │           ▼                    │         │
                  │  ┌─────────────────────────┐  │         │
                  │  │ 内容生成                  │  │         │
                  │  │ LLM 撰稿 · 深度解读        │  │         │
                  │  │ before/after 定位         │  │         │
                  │  │ 工程共鸣 · 观点输出        │  │         │
                  │  └─────────────────────────┘  │         │
                  │           │                    │         │
                  │           ▼                    │         │
                  │  ┌─────────────────────────┐  │         │
                  │  │ 富媒体处理                │  │         │
                  │  │ LaTeX 公式 → SVG → 微信CDN│  │         │
                  │  │ PDF 论文原图 精准裁剪      │  │         │
                  │  │ 封面渐变图 自动生成        │  │         │
                  │  └─────────────────────────┘  │         │
                  │           │                    │         │
                  │           ▼                    │         │
                  │  ┌─────────────────────────┐  │         │
                  │  │ 自进化训练               │ ◀┼─────────┼──────┐
                  │  │ 阅读数据 → 选题策略        │  │         │      │
                  │  │ 风格迭代 · 话题优化        │  │         │      │
                  │  └─────────────────────────┘  │         │      │
                  └───────────────┬───────────────┘         │      │
                                  │                          │      │
                                  ▼                          │      │
  ┌───────────────────────────────────────────────────┐     │      │
  │              ④ Publish ─ 多平台分发                │     │      │
  │                                                   │     │      │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────┐│     │      │
  │  │ 公众号    │  │  知乎    │  │  掘金    │  │CSDN││     │      │
  │  │ 草稿箱    │  │  草稿     │  │  草稿    │  │草稿││     │      │
  │  └──────────┘  └──────────┘  └──────────┘  └────┘│     │      │
  │                                                   │     │      │
  │  一条命令 · wechatsync 引擎 · 30 秒搞定              │     │      │
  └───────────────────────┬───────────────────────────┘     │      │
                          │                                  │      │
                          ▼                                  │      │
  ┌──────────┐    ┌──────────┐    ┌──────────┐              │      │
  │⑤Analytics│───▶│⑥ Profile │───▶│⑦Strategy │──────────────┘      │
  │ 数据采集  │    │ 用户画像  │    │ 策略复盘  │  数据反哺自进化       │
  │ 阅读量    │    │ 兴趣分布  │    │ 选题推荐  │                      │
  │ 分享/在看 │    │ 阅读偏好  │    │ 风格建议  │                      │
  └──────────┘    └──────────┘    └──────────┘                      │
                                                                     │
  ◀────────────────────────── 飞轮闭环 ──────────────────────────────┘
```

### 流程详解

| 步骤 | 做了什么 | 关键能力 |
|------|---------|---------|
| ① **Learn** | 论文原文获取（arXiv / PDF / 源码） | 学习笔记 → 进度追踪 |
| ② **Write** | LLM 撰稿 + 人设 + 富媒体 + 自进化 | 见下方展开 |
| ③ **Review** | LLM 对比论文原文逐句核查 | 分级报告（error/warning/suggestion） |
| ④ **Publish** | 一键同步 4 平台草稿箱 | wechatsync 引擎，30 秒完成 |
| ⑤ **Analytics** | 定时采集阅读/在看/分享数据 | 公众号后台自动抓取 |
| ⑥ **Profile** | 构建用户兴趣画像 | 基于历史阅读数据 |
| ⑦ **Strategy** | 周策略复盘 → 选题推荐 | 数据反哺 ② Write（自进化） |

### ② Write 展开：人设 + 自进化

撰文不是「把论文翻译一遍」。Paper Loop 的 Write 环节是一个**有人设、会进化**的 AI 写作引擎。

**人设层 — 你定义风格，AI 遵循风格**

人设不是硬编码的——它是一个**用户可配置的配置文件**。每个人的文章都应该有自己的声音。Paper Loop 内置一份示例人设，你可以直接使用，也可以另写一份。

内置示例（基于作者 kk 的真实写作风格）：

```toml
# persona.toml — 用户可自定义的写作人设
# 内置示例：INTJ 工程师视角

[identity]
role = "后端工程师，从零学 AI，用自己的方式理解技术"
tone = "理性克制，独立思考，直击本质"
audience = "工程侧同学，不需要看懂所有公式，但读完必须有收获"

[writing]
analogy_style = "工程类比优先 — 用缓存/API/分布式/代码Review 讲 DL"
judgment_style = "敢下判断，不自注解 — 不说「这很重要」，直接说哪里重要"
language_style = "中文原生表达 — 禁用「值得注意的是」「退一步讲」「应运而生」"
ending_style = "具体判断收尾 — 不展望「未来可期」，不写「路还长」"

[prohibited]
phrases = [
    "值得注意的是", "退一步讲", "总而言之", "综上所述",
    "应运而生", "层出不穷", "方兴未艾", "蔚然成风",
    "这说明了一个道理", "这个故事告诉我们"
]
patterns = [
    "结尾展望式金句（「未来已来」「路还长」）",
    "PPT 式逐条罗列（bold 人名 + 统一句式）",
    "宣告式比喻引入（「打个比方」「这就好比」）",
    "blockquote 一句话总结"
]

[structure]
core_insight_first = true   # 核心判断前置（前 3 段内）
how_layer_depth = 2         # 实操穿透：不只 what/why，必须讲 how
aside_count = "3-5"         # 灰色斜体旁注：工程洞察，每句 1-2 行
ending_section = "写在最后"   # 结尾：重新框定问题或留下可辩论的判断
```

> 人设文件路径：`config/persona.toml`。想换成学术科普风？产品经理视角？创业者口吻？改这个文件就行。文章的声音从你的配置文件来，不从代码里来。

**自进化层 — 文章不是越写越熟练，是越写越精准**

```
  ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ 发布文章  │────▶│ 回收数据  │────▶│ 策略复盘  │
  └──────────┘     └──────────┘     └──────────┘
        │                                  │
        │        ┌─────────────────┐       │
        └───────▶│ 反哺下一篇文章   │◀──────┘
                 │ · 话题优化       │
                 │ · 风格校准       │
                 │ · 发布时间       │
                 │ · 篇幅调整       │
                 └─────────────────┘
```

| 数据信号 | 如何反哺撰文 |
|---------|-------------|
| 阅读量高的文章共性 | 优先复现：工程类比多、判断句有力、标题有钩子 |
| 阅读量低的模式 | 避免：过于学术、缺少观点、标题平淡 |
| 分享/在看数据 | 判断句截图率 → 调整判断句密度和位置 |
| 粉丝增长曲线 | 话题匹配度 → 调整选题方向 |
| 平台差异数据 | 同一篇文章在不同平台的表现 → 平台定制策略 |

> 策略文件在 `data/weekly_strategy.json`，每篇新文章撰写前自动读取，融入写作决策。

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
