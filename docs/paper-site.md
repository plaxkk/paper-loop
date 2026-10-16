# Paper Loop 网站

网站在 `site/`；独立论文服务在 `services/paper_api/`。原有 Python 流水线与本地配置没有迁移。网站不会读取或发布 `data/` 中的私人文章、账号信息和运营数据。

云端部署见 [单项目 Vercel + Supabase 部署说明](deployment.md)。

## 本地运行

要求 Node.js 24、Python 3.10+。从仓库根目录执行：

```sh
python3 -m venv .venv-site
.venv-site/bin/pip install -r services/paper_api/requirements.txt
cp services/paper_api/.env.example .env
```

在 `.env` 填写自己的 `PAPER_LLM_API_KEY`、模型名和 OpenAI-compatible 服务地址。API 与 Worker 必须使用同一组配置、同一数据目录。服务不会执行或读取 shell 配置，不会自动复用微信凭据。

终端一：

```sh
set -a
. ./.env
set +a
.venv-site/bin/python -m uvicorn services.paper_api.app:app --host 127.0.0.1 --port 8000 --no-access-log
```

终端二（同样先加载 `.env`）：

```sh
set -a
. ./.env
set +a
.venv-site/bin/python -m services.paper_api.worker
```

终端三：

```sh
cd site
npm ci
npm run dev
```

访问 http://localhost:3000。无需模型密钥也能使用经典栏目、PDF 原文、进度与历史；AI 翻译、解读和对话会明确提示未配置，不生成模拟结果。PDF.js Worker 在 dev/build 命令中显式复制，兼容禁用 npm install 生命周期脚本的环境。

## 单机 Docker Compose

安装 Docker 后，在根目录配置 `.env`，执行：

```sh
docker compose up --build -d
```

打开 http://localhost:3000。网关只绑定回环地址，适合本机使用或置于 HTTPS 反向代理之后。对外提供服务时设置正确的 `PAPER_PUBLIC_ORIGINS=https://你的域名` 和 `PAPER_SECURE_COOKIE=true`，并在外层配置 HTTPS。API、Worker、网站使用内部网络，只有网关暴露端口。SQLite 与私有 PDF 保存在 `paper-data` 命名卷中；不要把该卷当成静态站点目录发布。

公开上线前，人工审核经典文章，并在隐私页补充实际模型服务商及其数据政策。内容状态区分公众号原稿归档（archived）与编辑初稿（draft），归档没有代替新一轮人工审核。当前机器没有 Docker，本次交付只静态检查部署配置，未声称完成容器启动验收。

## 内容维护

`site/content/classics/*.md` 使用 数据格式固定为 JSON 的 frontmatter 和 Markdown 正文。字段包括标题、原始日期、主题、阶段、来源、arXiv 编号、术语与审校状态。论文按首次公开日期排序，阶段仅是阅读编排，不表示直接因果关系。

发布前：核对论文版本、方法和实验条件；复核数字、公式、图片署名与后续影响；然后把 `status: draft` 改为 `reviewed`；`archived` 表示直接迁入的公众号原稿，迁移记录见 [已发表文章迁移](published-classics.md)。不要整体导入 `data/`，不要把公众号 CDN 当成网站必须依赖。Transformer 示例图的权利与署名见 `site/public/papers/ATTRIBUTION.md`。

## 数据与后台任务

- 匿名 Cookie 是随机令牌，服务端只保存哈希；不使用设备指纹。
- 所有工作台、PDF、消息、任务、进度与删除接口均检查会话归属。
- 上传以文件哈希在同一会话内去重；arXiv 支持编号、HTTPS 摘要页/PDF 地址，固定下载版本。无版本的相同导入在本会话内恢复已有工作台；读取新版本可明确输入 `vN`。
- 模型返回的引用必须是当前论文的原文块 ID。模型引用有效不代表结论正确，需人工核对语义。
- 长文按块分批生成摘要；问答对整篇正文及附录打分检索。当前采用关键词、中文领域词映射和已有论点引用加权，不是完整语义检索系统。
- 本地任务存储在 SQLite WAL；云端存储在 Supabase PostgreSQL，由专用鉴权的 Vercel 函数执行。Worker 原子认领并续租；中途崩溃后租约到期可恢复。远程调用结束时再检查任务归属，避免删除后写回。
- 每个匿名会话每天 3 次新导入、50 次主动 AI 操作（失败重试也占额度），UTC 零点重置。缓存结果和重复请求不重复扣次数。删除历史不重置配额。
- 默认全站每天 5000 次 AI 操作，导入上限为其五分之一；可通过 `PAPER_GLOBAL_DAILY_ACTIONS` 调整。单次分析可能包含多次模型调用，这不是金额级硬预算。
- Compose 网关额外按来源 IP 限速，访问日志关闭；本地裸 API 只应绑定回环地址。限额不能彻底阻止重置 Cookie，需要实际流量后再决定更强的滥用防护。

Worker 每小时清理：工作台从创建起 30 天到期，不无限续存；消息/任务也受创建时间上限限制。清空历史级联删除文件、生成结果、消息、任务和关联明细，已去标识的聚合统计不反向恢复。聚合最长保留 180 天。备份如有启用，也应采用相同保留边界；本版本未自动配置外部备份。

内部统计与手动清理：

```sh
python3 -m services.paper_api.analytics
python3 -m services.paper_api.analytics --cleanup
# Compose 中：docker compose exec api python -m services.paper_api.analytics
```

报告包含按天事件、问题分类、Token 与耗时总量、导入成功率、有效交互率、经典连续阅读点击率代理、匿名浏览器七日回访率。原始问题只存在私人对话/任务中，不复制到分析事件。没有样本的指标返回 null。

## 验证

```sh
pip install -r services/paper_api/requirements-dev.txt
python3 -m pytest services/paper_api/tests tests -q
cd site
npm run typecheck
npm run build
# 先启动 API、Worker 和站点：
PAPER_TEST_PDF=/绝对路径/英文文字版论文.pdf npm run test:e2e
```

浏览器验收优先使用本机 Chrome，macOS 默认探测 `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`。其他平台可通过 `PAPER_CHROME_PATH` 指定 Chromium；没有本机 Chrome 时使用已安装的 Playwright 浏览器。截图在 `site/test-results/screenshots`。

后端 30 个固定问题使用受控模型替身验证消息、引用、去重与分析数据流；**这些不是实测 AI 内容质量的证据**。配置真实密钥后可显式运行 30 题 Transformer 原文评测（会产生模型费用）：

```sh
python3 -m services.paper_api.evaluate --live --paper /绝对路径/transformer.pdf
```

结果默认保存到被忽略的 `state/paper-api/evaluation.json`，需人工核对数字、证据支持与“依据不足”回答。若没有配置模型，本次不会伪造真实模型验收结果。
