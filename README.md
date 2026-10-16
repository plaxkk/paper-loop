# Paper Loop · AI 论文阅读与解读

面向有编程基础的中文 AI 学习者：沿经典论文时间线理解大模型的发展，在论文工作台中阅读原文、翻译段落并追问。仓库也保留原有的 Python 论文写作与多平台分发工具链。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)


## 网站 MVP

在线访问：[paper-loop-xi.vercel.app](https://paper-loop-xi.vercel.app)。前端与论文 API 使用同一个 Vercel 项目 `paper-loop`，数据库与私有 PDF 存放在 Supabase；AI 按当前配置暂未启用。

| 栏目 | 已实现能力 |
|---|---|
| 经典论文路线 | 2017—2023 年 12 篇论文、纵向时间线、主题筛选、中文解读、公式和前后篇导航 |
| 论文工作台 | 上传 PDF / 导入 arXiv、PDF.js 原文阅读、页码与段落定位、论点与提醒、按需翻译和带引用的问答 |
| 阅读历史 | 当前匿名浏览器恢复论文、页码、译文和对话；单篇或全部删除 |

首批 12 篇解读是**待人工审校的编辑初稿**。AI 功能需要后端配置模型密钥；未配置时仅提供 PDF 原文阅读，并明确提示状态。文字型 PDF 上限 30 MB、100 页，暂不支持扫描件 OCR、图表视觉解释或译文 PDF 导出。

- [本地启动与维护](docs/paper-site.md)
- [云端部署：单个 Vercel 项目 + Supabase](docs/deployment.md)
- [验收记录与尚未完成的检查](docs/paper-site-verification.md)

### 本地快速启动

```sh
python3 -m venv .venv-site
.venv-site/bin/pip install -r services/paper_api/requirements.txt
cp services/paper_api/.env.example .env
cd site && npm ci
```

填写 `.env` 后，分别启动 API、Worker 和网站；完整命令见运行说明。网站要求 Node.js 24，后端要求 Python 3.10+。也可从仓库根目录执行 `docker compose up --build`，访问 `http://localhost:3000`。

### 网站架构与数据

云端：浏览器 → 单个 Vercel 项目（Next.js + FastAPI Services）→ Supabase PostgreSQL / 私有 Storage。Supabase 的任务触发器与每分钟兜底检查通过专用鉴权唤醒同项目的后台任务接口；长篇 AI 任务按步骤保存检查点。Vercel Services 当前为 Beta。模型调用只在后端发生，密钥不进入浏览器。

本地：Next.js → FastAPI + 独立 Worker → SQLite WAL / 私有文件目录；Docker Compose 使用独立容器和共享持久卷。

匿名会话通过 HttpOnly Cookie 识别。论文、对话和阅读记录保留 30 天，去标识聚合指标保留 180 天；清除 Cookie 后无法自动恢复旧历史。每个匿名会话每天最多导入 3 篇论文、执行 50 次主动 AI 操作，另有全站限额。用户上传内容不会进入经典栏目。

## 原有内容工具链

以下为保留的 Python CLI 与分发工作流。网站使用独立服务和配置，不会自动读取私人文章、微信凭据或运营数据。

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
  └──────────┘    │  │ 自定义风格 · 工程类比       │  │    │ 可读性    │
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

以下为通用写作偏好示例，可按需保存在本地人设文件中：

```toml
# persona.toml — 用户可自定义的写作人设
# 示例：工程师视角

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

> 将偏好写入 `data/private/persona.md`，并在本地配置中设置 `persona_file`。此文件由执行 Skill 的 Agent 在撰稿前读取；Python 审稿命令不会自动读取人设。上述 TOML 仅用于说明偏好结构，不是已实现的 TOML 配置接口。

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
pip install -e .
npm install -g @wechatsync/cli
```

### 本地配置与个人信息

```bash
cp data/config.json.example data/config.local.json
chmod 600 data/config.local.json
mkdir -p data/private
# 在 data/private/persona.md 中填写自己的写作偏好
```

编辑本地配置，填写自己的值。此文件和 `data/private/` 均被 Git 忽略，公共模板只包含空值和通用默认值。

| 配置项 | 用途 | 可覆盖它的环境变量 |
|---|---|---|
| `wechat_appid` / `wechat_appsecret` | 微信 API 凭据 | `WECHAT_APPID` / `WECHAT_APPSECRET` |
| `author` | 发布文章的默认署名，单篇文章 `author` 优先 | `PAPER_LOOP_AUTHOR` |
| `cover_tagline` | 封面底部文字 | `PAPER_LOOP_COVER_TAGLINE` |
| `wechatsync_token` | 多平台分发凭据 | `WECHATSYNC_TOKEN` |
| `llm.api_key` | 审稿模型密钥 | `llm.api_key_env` 指定的变量，默认 `DEEPSEEK_API_KEY` |
| `llm.base_url` / `llm.model` | 审稿服务地址和模型 | `PAPER_LOOP_LLM_BASE_URL` / `PAPER_LOOP_LLM_MODEL` |
| `persona_file` | 本地写作偏好、渠道偏好，供 Agent 读取 | — |
| `study_plan_file` / `progress_file` | 本地学习计划与进度，供 Agent 读取 | — |

发布、封面生成、审稿和分发模块按如下顺序选择一个配置文件（不合并）：

1. 显式设置的 `PAPER_LOOP_CONFIG` 路径；设置后文件必须存在。
2. `data/config.local.json`。
3. `~/.paper-to-wechat/config.json`。
4. 旧版 `data/config.json`，兼容 `appid` / `appsecret` 字段。

环境变量优先于文件中对应字段。未配置署名时使用空字符串，封面默认显示“论文学习笔记”。运行数据仍保存在仓库内的 `data/`；上述配置不改变采集服务端口或数据目录。旧的 `pipeline.config.Config` 接口保留兼容，其配置逻辑独立于这些模块。

人设文件路径相对仓库根目录解析。真实账号数据、私人合作关系和个人操作记录应放在 `data/private/`，公共 Skill 只保留通用流程。

**从旧版迁移**：将原有配置复制到 `data/config.local.json`，再添加所需字段。审稿与分发不再自动读取 `~/.zshrc` 或 Hermes 配置；请将相关密钥放入本地配置或显式导出相应环境变量。不要把密钥写进 README、文章或 Skill。

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
├── site/                  # Next.js 网站、经典内容、PDF 阅读组件
├── services/paper_api/    # FastAPI、持久任务 Worker、隐私与分析
├── docs/                  # 运行、部署与验收记录
├── vercel.json            # 单项目 Next.js + FastAPI 服务路由
├── supabase/migrations/   # 私有数据库、Storage 与任务唤醒
├── render.yaml            # 可选持久磁盘部署方案，当前未使用
├── compose.yaml           # 本地 / 单机容器部署
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

## 隐私与开源发布

- 微信凭据、模型密钥、分发 Token 仅保存在本地配置或环境变量；`data/` 除公开配置模板外默认全部忽略。
- Token 缓存、邮箱配置、数据库、采集原始响应、草稿、运营报告和本地人设不应公开。`.gitignore` 无法阻止强制添加，也不会清除过去的提交。
- **不要直接压缩工作目录发布**，其中可能含有被忽略的真实凭据。审阅并提交脱敏改动后，使用 `git archive --format=zip --output=paper-loop-source.zip HEAD` 导出已提交文件；该压缩包不包含 Git 历史。
- 将已有私有仓库改为公开前，必须检查所有分支、标签与提交历史，以及 Issues、PR、附件和 Actions 日志。删除最新版文件不会移除旧提交中的内容。
- 若历史曾包含真实密钥，先撤销或轮换，再清理历史。若只希望发布当前干净版本，可将审阅后的源码导出到新仓库，以新的初始提交开源；不要把旧 `.git` 目录复制过去。
- 分发由本地浏览器扩展对接目标平台；审稿会向配置的模型服务发送论文和文章内容，发布及图片上传会将相应内容发送到目标平台。

---

## License

MIT License. 详见 [LICENSE](LICENSE) 文件。
