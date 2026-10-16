# 网站 MVP 验收记录

本记录区分真实源验证、受控测试与尚未完成的验收。

## 已完成

- Next.js 生产构建通过，经典内容静态生成，工作台动态加载。
- 新论文服务 57 项 pytest 通过；原有项目 84 项 pytest 通过。
- 4 项本机 Chrome 端到端测试通过：桌面经典页面/筛选/公式/主题；手机导航与导入；真实 PDF 上传/渲染/进度恢复/会话隔离/删除；明确的受控 AI 接口下的论点/翻译/对话/引用跳转。
- 真实 Transformer PDF：15 页、376 个正文块、38,810 字符，含附录；超过旧模块 15,000 字符截断限制。
- 真实 arXiv 无版本导入解析为 1706.03762v7，成功下载，标题识别为 Attention Is All You Need。export API TLS 失败时，回退到官方摘要页的版本历史，不关闭证书校验。
- 新网站生产依赖 npm 审计 0 告警。
- Compose YAML 静态解析通过，包含 gateway、site、api、worker 与私有持久卷。
- 截图目录：site/test-results/screenshots（忽略版本控制）。

## 验收限制

- 没有配置真实模型密钥，未声称通过真实模型翻译/回答质量验收。30 个固定问题的 pytest 使用模型替身；另提供显式 --live 的真实模型评测脚本，输出需人工复核。
- 网站现有 13 篇经典内容：12 篇已复用公众号原稿、状态为 archived；DPO 仍为 draft。迁移没有代替新一轮技术审校。
- 本机未安装 Docker，尚未运行 docker compose build/up；部署文件只完成静态检查。
- Lighthouse 本地测试不是生产网络的 Core Web Vitals 保证。

## 最终预览状态

最后一次预览重启的自动权限审查连续超时，因此没有把该次重启计为成功。先前四项 Chrome 端到端和截图验收已完成；最后补充了对比度、标题层级和图标修复，生产构建通过。Lighthouse 首轮评分：性能 93、可访问性 93、最佳实践 96、SEO 100；修复后复测因预览未能重启而未完成，不虚报新评分。

本地 API 和 Worker 已启动；网站可在 site/ 执行 npm run start 恢复。

## 云部署与迁移验证（2026-10-16）

- SQLite 模式论文服务 69 项、原项目 84 项测试通过，共 153 项；新增 Storage HEAD 返回 400/404 与鉴权、服务异常的兼容检查。
- 隔离的本地 PostgreSQL 实例运行 61 项服务与 Serverless 测试通过，覆盖配额、归属、级联删除、任务租约、上传校验、删除队列和翻译检查点；2 项单机进程启动器测试单独在 SQLite 套件中通过。
- TypeScript 检查与 Next.js 生产构建通过。单个 Vercel 项目的 Next.js + FastAPI Services 构建成功并推广到生产域名。
- 新 Supabase 项目已应用私有数据迁移，9 张表开启 RLS、anon 无 SELECT 权限，PDF bucket 为私有。未创建付费资源，未启用 AI。
- 独立 `paper-loop-api` 项目已暂停；部署入口统一为 `paper-loop`。
- 用户更新 Production 数据库连接串后，修正密码特殊字符的 URL 编码并重新部署。生产会话返回 200，确认直传开启、AI 关闭。
- 后台调度迁移已应用：任务触发器与每分钟兜底任务启用，专用鉴权调用返回 200，公开调用返回 404。
- 生产链路实测：5,245,377 字节 PDF 签名直传返回 200，后台自动解析为 2 页 / 4 个正文块，私有文件读回一致；其他会话返回 404，页码和历史恢复正常，AI 操作明确返回 503。删除后数据库论文、任务、关联事件、Storage 对象及删除队列均为 0。
- 安全检查：9 条 RLS 无策略 INFO 对应私有 schema 的默认拒绝设计。pg_net 安装产生 1 条 [extension_in_public 提醒](https://supabase.com/docs/guides/database/database-linter?lint=0014_extension_in_public)：扩展元信息位于 public，实际函数位于 net，public 中属于该扩展的函数为 0；该扩展不可直接迁移 schema，未修改系统目录或放宽权限。
- 内置浏览器已打开生产站点，实际完成 5 MB PDF 上传、自动解析、PDF.js 原文渲染与翻页。刷新后恢复到第二页；真实 Transformer v7 从 arXiv 云端导入，15 页 / 376 块 / 38,810 字符（含附录）。线上阅读器截图保存于 `/private/tmp/paper-loop-live-reader.jpg`（未提交）。

## 已发表公众号文章迁移（2026-10-16）

- 已直接迁入 12 篇原稿、31 张原图；GPT-1 选择与已发表标题匹配的版本，补入 FlashAttention-2，网站共 13 个时间线节点，DPO 保持原有 draft。
- 核对全部原有保留文本片段与原标题，未发现遗漏；31 张图片可本地解码，正文不依赖微信 CDN。
- TypeScript 检查与生产构建通过，生成 22 个路由。
- 本地浏览器核验 Transformer 原稿 81 个段落、7 个章节，目录无失效定位，原图正常加载，无 Markdown 加粗标记泄漏。390 px 手机视口的文档宽度同为 390 px，未发生水平溢出。
- 桌面与手机截图位于 `/private/tmp/paper-loop-published-desktop.jpg` 与 `/private/tmp/paper-loop-published-mobile.jpg`。
- 本次是原稿内容迁移与网页排版验证，不作为对原稿技术结论的新一轮人工审校；具体迁移范围与后续维护项见 [迁移记录](published-classics.md)。
