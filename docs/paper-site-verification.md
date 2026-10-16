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
- 12 篇经典文章是新整理的编辑初稿，status=draft；没有代替用户完成人工审核。
- 本机未安装 Docker，尚未运行 docker compose build/up；部署文件只完成静态检查。
- Lighthouse 本地测试不是生产网络的 Core Web Vitals 保证。

## 最终预览状态

最后一次预览重启的自动权限审查连续超时，因此没有把该次重启计为成功。先前四项 Chrome 端到端和截图验收已完成；最后补充了对比度、标题层级和图标修复，生产构建通过。Lighthouse 首轮评分：性能 93、可访问性 93、最佳实践 96、SEO 100；修复后复测因预览未能重启而未完成，不虚报新评分。

本地 API 和 Worker 已启动；网站可在 site/ 执行 npm run start 恢复。

## 云部署与迁移验证（2026-10-16）

- SQLite 模式论文服务 63 项、原项目 84 项测试通过，共 147 项。
- 隔离的本地 PostgreSQL 实例运行 61 项服务与 Serverless 测试通过，覆盖配额、归属、级联删除、任务租约、上传校验、删除队列和翻译检查点；2 项单机进程启动器测试单独在 SQLite 套件中通过。
- TypeScript 检查与 Next.js 生产构建通过。单个 Vercel 项目的 Next.js + FastAPI Services 构建成功并推广到生产域名。
- 新 Supabase 项目已应用私有数据迁移，9 张表开启 RLS、anon 无 SELECT 权限，PDF bucket 为私有。未创建付费资源，未启用 AI。
- 独立 `paper-loop-api` 项目已暂停；部署入口统一为 `paper-loop`。
- **当前阻塞**：生产 API 从 Supabase 收到数据库密码认证失败，需在 `paper-loop` 更新正确的 `PAPER_DATABASE_URL` 后重新部署。已修正原 URL 中未编码的特殊字符；修正 URL 格式不等于密码验证通过。
- 后台调度已获用户授权，迁移文件已准备；待数据库连通后安装并验证。真实 Storage 上传、大文件直传、云端自动解析和删除尚未完成验收，不以 Vercel READY 代替端到端验证。
- 本机浏览器访问生产域名曾遇到连接失败，平台 CLI 可取得实际运行错误；尚未取得云端浏览器完整流程的验收结果。
