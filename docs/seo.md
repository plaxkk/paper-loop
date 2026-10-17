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

2026-10-17：技术配置完成、本地生产构建和渲染检查通过。搜索平台验证与提交回执将在生产部署后补记。实际收录和排名需由各搜索引擎处理，不能通过本次技术检查推断。

## 后续关注

以 Search Console 的索引覆盖、实际搜索词、展示、点击和页面体验为基线。新站没有足够真实用户数据时，不编造 Core Web Vitals、流量或 SEO 分数。优先完善已有解读的内部链接与论文来源，持续发布经复核的原创内容；不批量制作近似关键词页，也不自动改写已发表文章。
