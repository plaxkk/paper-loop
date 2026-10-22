# 云端部署：一个 Vercel 项目 + Supabase

网站地址：[paper-loop.kkplayit.online](https://paper-loop.kkplayit.online)。GitHub 仓库为 `plaxkk/paper-loop`，生产分支为 `main`。前端和论文 API 都运行在 **`paper-loop` 这一个 Vercel 项目**，不需要另建 `paper-loop-api`。

## 服务结构

根目录 `vercel.json` 使用 [Vercel Services](https://vercel.com/docs/services)：`site/` 的 Next.js 提供页面，`services/` 的 FastAPI 处理 `/api/*`。Services 当前为 Beta；部署 CLI 固定使用 `npx vercel@64.0.2`。项目 Root Directory 留空，Framework、Build/Install Command 使用根配置，不再设置为 `site`。

数据存放于 Supabase 项目 `xnjyeklbpuklmatifpbo`：

- `paper_loop` 私有 schema：匿名会话、论文正文、任务、译文、对话、配额与统计。所有表开启 RLS，撤销 anon/authenticated 权限；后端通过私有数据库连接访问，并逐次校验匿名会话归属。
- `paper-pdfs` 私有 Storage bucket：PDF 由浏览器使用单对象签名地址直接上传，绕开 Vercel 函数请求体限制；服务端校验 SHA-256 与实际大小。阅读时经归属校验返回 60 秒签名地址。
- 数据库任务触发器通过 `pg_net` 唤醒同项目 `/api/internal/tick`；`pg_cron` 每分钟检查遗漏任务、过期租约与删除队列，空闲时只按小时触发清理。请求携带 Vault 中的专用密钥，接口不允许公开调用。

每次函数只认领一个任务步骤。长篇解读与翻译保存检查点后重新入队，每步最多一次模型请求；失败可重试，进程中断后最多等待 10 分钟租约过期。`/tmp` 仅作调用内缓存，原文件和结果均不依赖 Vercel 本地磁盘。

## 环境变量（仅在 paper-loop 配置）

在 Vercel 项目 Settings → Environment Variables 的 Production 环境配置：

| 变量 | 用途 |
|---|---|
| `PAPER_DATABASE_URL` | Supabase Connect 的 Transaction pooler URL，端口 6543；密码中的 `@`、`#`、`/` 等必须 URL 编码。后端强制远程 TLS，关闭 prepared statements 以兼容事务池 |
| `PAPER_SUPABASE_URL` | `https://xnjyeklbpuklmatifpbo.supabase.co` |
| `PAPER_SUPABASE_SECRET_KEY` | 同项目后端 Secret key，标记 Sensitive，绝不使用 `NEXT_PUBLIC_` 前缀 |
| `PAPER_SERVERLESS` | `true` |
| `PAPER_SECURE_COOKIE` | `true` |
| `PAPER_PUBLIC_ORIGINS` | `https://paper-loop.kkplayit.online,https://paper-loop-xi.vercel.app`，精确校验写入请求的 Origin |
| `PAPER_WORKER_SECRET` | 随机、至少 32 字符的专用密钥，与 Supabase Vault 的 `paper_loop_worker_secret` 相同 |
| `PAPER_LLM_API_KEY` | **当前留空，不启用 AI** |
| `PAPER_LLM_BASE_URL` / `PAPER_LLM_MODEL` | 日后启用 AI 时再配置对应接口与模型 |

云端不需要 `PAPER_API_URL`；根服务路由直接处理同源 API。Supabase 使用哪个账号不取决于浏览器登录账号，而由每个项目的上述 URL 和密钥决定。MCP 授权仅供开发管理，不替代运行时凭据。

## 首次部署与后续更新

1. 在目标 Supabase 项目应用 `supabase/migrations/20261016102651_paper_loop_cloud.sql`，创建私有数据表和 Storage bucket。
2. 在 Supabase Vault 安全写入 `paper_loop_worker_secret`，与 Vercel 对应变量一致。不要把密钥写进 SQL 迁移文件或提交记录。
3. 配置上述环境变量，从仓库根目录部署：

   ```sh
   npx vercel@64.0.2 deploy --prod
   ```

4. 确认 `/api/health` 返回 `{"status":"ok"}` 后，应用 `supabase/migrations/20261016104140_paper_loop_dispatch.sql`。调度目标仍为 `https://paper-loop-xi.vercel.app/api/internal/tick`；平台把 `/api/*` 直接路由到 FastAPI，不参与前端页面跳转，因此本次更换生产页面域名无需修改数据库调度或密钥。
5. 后续推送 `main` 由 Git 集成自动部署。检查 Vercel 的 Git commit SHA 和 READY 状态，再验证实际请求。

`.vercelignore` 只上传网站与服务源代码，排除本地状态、PDF、环境文件、测试与 Git 历史。Python 云运行时使用 3.13，服务运行依赖在 `services/requirements.txt`；修改依赖时同步 `services/paper_api/requirements.txt`。

## 验收与运维

检查经典栏目、上传小 PDF 和超过 4.5 MB 的 PDF、自动解析、原文读取、页码恢复、两个匿名会话隔离及删除。AI 未启用时必须明确提示，不生成模拟译文或对话。真实模型启用后再进行 30 题质量验收。

检查 `cron.job` 的 `paper-loop-worker`、`net._http_response` 的响应状态及 Vercel 运行日志，勿输出鉴权请求头。工作台删除与到期清理将文件写入持久删除队列；Storage 暂时不可用时保留队列，下一次唤醒重试。私人内容 30 天、聚合统计 180 天；如另启备份，应对备份制定同等保留与删除策略。

Vercel 可回滚代码部署；数据库迁移不会随代码回滚。暂停后台调用时先 `cron.unschedule('paper-loop-worker')` 并移除任务唤醒触发器，保留任务数据后再恢复。不要通过关闭 RLS 或公开 bucket 排查故障。

本次不启用付费方案和模型调用，但平台免费额度仍会被数据库、存储和函数使用消耗。`render.yaml` 保留为可选单实例持久磁盘方案，当前未创建或使用 Render 资源。本地 SQLite、独立 Worker 与 Docker Compose 的启动方式见 [运行说明](paper-site.md)。

## 2026-10-22 域名迁移发布

生产部署 `dpl_HQDnWTrXYHBG36aLNMgGw3z6QobL` 已提升到正式域名。补齐 10 月 19 日准备但未正式启用的 canonical、sitemap、robots 与旧域名 HTTP 308 跳转，并为新域名加入 Naver 的 HTML 所有权验证标签。原 Naver 标签保留，避免旧站验证意外失效。

构建、TypeScript 和 `scripts/check_seo.py` 通过；线上 17 个公开地址、规范链接与新 sitemap 已核对。Google 新地图提交及地址更改已受理，Bing 新地图 Processing，Naver 待人工验证码，状态见 [SEO 记录](seo.md)。

已知独立故障：旧生产构建与本次构建的 `/api/health` 均返回 500；前端域名迁移未改变后端配置。候选检查返回错误时，临时发布命令未停止而继续了 promote；后续发布应先单独核验结果，或使用 `set -e` / `&&` 确保失败阻断。不得把此次公开页面检查通过写成 API 健康检查通过。

最终整合版本同时保留远端 PR #1 的 `@vercel/analytics` 集成。首次迁移构建遗漏该集成，发现后已合并远端提交并重新构建，后续发布必须以整合版本为准。新 Naver 标签置于同名标签列表首项，旧标签继续保留。

Naver 官方验证文件于 2026-10-22 从误放的 Nestful 目录移到本项目根目录，并将同字节副本放到 `site/public/`。发布提交 `38dd12c`，部署 `dpl_7iJF4qNTYguvLhcatwwupxHte88U` 已 READY 并绑定正式域名。公网验证文件与下载原件逐字节一致，Naver 所有权仍待新验证码与平台结果确认。
