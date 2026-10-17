# 网站 SEO 与搜索引擎提交

生产规范网址：https://paper-loop-xi.vercel.app

## 已实现

- 服务端输出各公开页面独立标题、描述和 canonical；工作台查询参数指向 `/workspace` 规范页。
- `/sitemap.xml` 提供 17 个公开网址：5 个公共页面与 12 篇已发表文章。初稿、阅读历史、私人工作台和 API 不在地图内。
- `/robots.txt` 提供站点地图地址；历史、私人阅读页和初稿同时使用页面 noindex。robots 不是权限控制，私人数据仍由 API 校验匿名归属。
- 已发表文章输出 BlogPosting 与 BreadcrumbList JSON-LD；作者 kk 对应可见署名和关于页。文章日期取公众号文章首发日期，论文年份单列；不编造更新时间、阅读量、资历或评分。
- 首页 WebSite 数据、中文语言声明、Open Graph / Twitter 分享卡片与原创封面。原配图含固有宽高，减少布局偏移；封面及时加载，后续图片延迟加载。
- 作者和内容来源见 `/about`。公众号原标题、正文、原配图保持不变，搜索标题独立配置。DPO 初稿不提交索引。
- Google、Bing、Naver 的公开站点验证标签保存在根布局；IndexNow 公开主机验证文件保留在 `site/public/`。它们不是服务端凭据，不要误删。

## 验证与维护

```sh
cd site
npm run build
cd ..
python3 scripts/check_seo.py
```

检查构建后的站点地图、所有预渲染公开页面的独立描述和 canonical、12 篇文章的日期和结构化数据、原图尺寸，以及初稿和历史的 noindex。

成功部署后手动运行：

```sh
python3 scripts/submit_indexnow.py
```

脚本先验证生产站点的主机证明文件，再读取生产 sitemap，仅将同域公开网址提交到 IndexNow 官方端点；不会上传 PDF、会话、私有数据或 API 密钥。HTTP 200/202 表示收到请求，不能据此宣称收录。Google 不使用 IndexNow，需在 Search Console 提交地图，必要时对重要网址请求编入索引。不要将普通文章提交到仅面向特定内容类型的 Google Indexing API。

新增文章前先检查状态与内容来源；公开文章自动进入下次构建的 sitemap。没有可靠修订日期时省略 lastmod，避免每次构建伪造更新。更换正式域名时同时更新 `site/lib/seo.ts`、IndexNow 主机证明配置、站长平台资源与规范地址，旧域名用 301 重定向。

## 提交记录

2026-10-17，生产部署 `dpl_HZ5qzeHR6HMxmUb5hZRJzAN71MHG`（代码提交 `aeb3357`）：

| 平台 | 回执与当前状态 |
|---|---|
| Google Search Console | HTML 标签验证成功；`/sitemap.xml` 提交成功，Google 显示“成功”、发现 17 个网页。首页实时检测显示“网址可编入 Google 索引”。 |
| Google 首页手动索引请求 | 已尝试，但平台提示今日每日配额已用完，未完成手动优先入队；不影响 sitemap 提交。检查时首页尚未收录。后续可在配额恢复后重试。 |
| Bing Webmaster Tools | HTML 标签验证成功；地图已提交，状态 Processing，等待抓取。 |
| IndexNow | 官方端点 `https://api.indexnow.org/indexnow` 返回 HTTP 202，接收 17 个公开网址。由协议通知参与的搜索引擎，包括 Bing、Yandex 等；不声称每个引擎均已单独验证或收录。Python TLS 连接异常后使用 curl 正常 TLS 提交成功。 |
| Naver Search Advisor | 用户完成人工验证码后，网站所有权验证通过；`sitemap.xml` 已显示在已提交列表，提交日期 2026-10-17。 |
| 百度 | 用户明确不纳入本次范围。 |

本地生产构建与 `python3 scripts/check_seo.py` 通过。线上 HTTP 验证 sitemap 为 200、17 个网址；robots 为 200 并引用规范地图；文章为 index；DPO 初稿与历史为 noindex；带 arXiv 查询参数的工作台 canonical 指向 `/workspace`。全部 17 个生产 sitemap 网页再次逐一核验，均为 HTTP 200，具有自指向 canonical、单一 H1、独立描述及可索引元数据。Chrome 核对文章可见署名、文章日期、论文年份、原文和导航。

“地图已读取”“网址可编入索引”“索引请求已收到”“实际收录”是不同状态。实际收录和排名需由各搜索引擎处理；不要根据本次回执承诺排名、收录数量或日期。

## 后续关注

以 Search Console 的索引覆盖、实际搜索词、展示、点击和页面体验为基线。新站没有足够真实用户数据时，不编造 Core Web Vitals、流量或 SEO 分数。优先完善已有解读的内部链接与论文来源，持续发布经复核的原创内容；不批量制作近似关键词页，也不自动改写已发表文章。

## 搜索意图与内容分工

- 首页：AI 经典论文中文解读、大模型论文学习，说明项目与两个入口。
- 时间线：大模型经典论文学习路线、Transformer 到对齐的发展阶段，承接学习顺序需求。
- 单篇文章：真实论文名称 + 论文解读 + 核心机制，例如“Transformer 论文解读：自注意力与多头注意力”“BERT 论文解读：双向预训练与掩码语言模型”。不改公众号正文来堆关键词。
- 工作台：PDF 与 arXiv 论文阅读工具，只描述当前可用能力；模型未启用时不在搜索摘要里承诺可用的 AI 翻译和对话。

这些是基于现有内容制定的页面分工，并非已经验证搜索量的关键词排名预测。积累 Search Console 搜索词数据后，再调整摘要和内容导航。

官方说明：[Google 站点地图](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)、[文章结构化数据](https://developers.google.com/search/docs/appearance/structured-data/article)、[IndexNow 协议](https://www.indexnow.org/documentation)、[Naver 所有权验证](https://searchadvisor.naver.com/guide/faq-start-register)。
