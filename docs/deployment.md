# 云端部署

前端部署到 Vercel，论文服务部署到有持久磁盘的 Render 单实例。Vercel 项目使用仓库的 `site/` 作为 Root Directory，GitHub 仓库为 `plaxkk/paper-loop`、生产分支为 `main`。

## 当前状态

- 网站前端：[paper-loop-xi.vercel.app](https://paper-loop-xi.vercel.app)，已完成 Vercel 生产构建与部署。
- 后端：部署配置已就绪，等待确认云账号与付费资源；当前线上工作台处于“准备中”。
- 模型：尚未配置真实模型密钥，未完成真实模型质量评测。

## 后端：Render

仓库根目录的 `render.yaml` 定义了可审阅的资源：新加坡区域、0.5 CPU / 512 MB 单实例、1 GB 持久磁盘。该方案使用付费资源，创建前须确认账户与费用。当前官方计价见 [Render Pricing](https://render.com/pricing)，计算、磁盘、超额流量与模型费用分别计算。

使用此仓库创建 Blueprint，填写环境变量：

| 变量 | 值 |
|---|---|
| `PAPER_PUBLIC_ORIGINS` | 网站的生产 HTTPS Origin；多个地址用英文逗号分隔，不带末尾斜杠 |
| `PAPER_LLM_API_KEY` | 在 Render 的秘密环境变量中配置；暂留空时仅支持 PDF 原文阅读 |
| `PAPER_LLM_BASE_URL` / `PAPER_LLM_MODEL` | 与密钥对应的模型接口和模型名 |
| `PAPER_SECURE_COOKIE` | `true` |
| `PAPER_API_DATA_DIR` | `/var/data/paper-loop`，必须位于挂载磁盘内 |

构建命令为 `pip install -r services/paper_api/requirements.txt`，启动命令为 `python -m services.paper_api.cloud`。启动器先初始化数据库，再启动 API 和 Worker；任一进程异常退出时结束另一个进程，让 Render 重启服务。端口读取平台的 `PORT`，健康检查为 `/api/health`。

SQLite、PDF、任务、译文和对话都保存在同一持久目录。不要创建分别挂载磁盘的 API 与 Worker 服务；Render 的一块磁盘只能被单个服务实例使用。此版本也不支持多副本。部署重启后未完成任务按持久租约重新执行，正在运行的任务最多等待现有 10 分钟租约到期。

## 前端：Vercel

项目设置：Framework 为 Next.js，Root Directory 为 `site`，Node.js 为 24.x。`site/vercel.json` 固定安装和构建命令。

后端健康检查通过后，在 Vercel 设置服务端环境变量 `PAPER_API_URL=https://你的论文服务域名`，重新部署。配置在构建时生成 `/api/*` 到后端的同源转发；不使用 `NEXT_PUBLIC_` 前缀。Vercel 模式拒绝本机 HTTP 后端地址。生产域名和自定义域名都需要加入后端 `PAPER_PUBLIC_ORIGINS`，预览域名需逐个加入。

没有设置云后端时，经典栏目仍可访问，工作台明确显示“准备中”并停止导入；私人接口返回 503。这个状态只用于逐步上线，不能作为完整后端部署成功的依据。

`.vercelignore` 限制 CLI 上传到网站源文件；`.env`、`data/`、`state/`、本地模型配置与 Git 历史均不应上传。

## 上线检查与回滚

1. 访问首页、时间线和任一经典详情页，检查静态文章内容。
2. 确认网站 `/api/health` 返回 `status: ok`，`/api/session` 能设置 Secure / HttpOnly Cookie。
3. 上传文字型 PDF，确认任务由 Worker 完成、PDF 可阅读；分别验证小文件及接近 30 MB 的文件经过 Vercel 入口后的上传限制。
4. 用两个浏览器会话验证论文归属隔离；刷新和重启后端后检查历史恢复，再验证删除清理。
5. 配置模型后验证翻译、引用定位与至少 30 个固定问题；未完成实测前不宣称模型质量验收通过。

前端可在 Vercel 回滚到上一个成功部署。后端可重新部署前一个 Git 提交，保留磁盘；代码回滚不会撤销数据变化。备份需覆盖 SQLite 一致性快照与私有 PDF，遵守 30 天私人数据保留期限；平台磁盘快照也需纳入保留与删除策略。
