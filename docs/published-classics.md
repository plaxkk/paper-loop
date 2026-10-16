# 公众号经典论文原稿迁移

这批内容按用户要求直接复用既有文章，正文没有重新生成。来源为仓库中的单篇文章 JSON，标题与本地最新一份已发表记录匹配。已发表记录只用于核对标题与日期；没有声称逐字抓取或校对了线上公众号版本。

## 已迁入

| 网站路径 | 原标题 | 已发表日期 | 原配图 |
|---|---|---|---|
| `/classics/transformer` | 不夸张地说，这篇论文，改变了整个AI的历史走向 | 2026-04-30 | 2 |
| `/classics/bert` | BERT的思路到底有多简单？简单到让人怀疑：这也行？ | 2026-04-30、2026-05-05 | 2 |
| `/classics/gpt-1` | GPT-1：第一次证明「先预训练，再微调」这条路走得通 | 2026-05-08 | 2 |
| `/classics/gpt-2` | OpenAI做了一次豪赌：不给任何指令，让模型自己学会所有任务 | 2026-05-10 | 2 |
| `/classics/gpt-3` | GPT-3：1750亿参数的豪赌，以及"涌现"这个改变一切的发现 | 2026-05-11 | 2 |
| `/classics/scaling-laws` | 大力出奇迹的背后：OpenAI找到了炼丹的物理定律 | 2026-05-12 | 3 |
| `/classics/chinchilla` | 越大越好？Chinchilla说：你可能练错了 | 2026-05-15 | 3 |
| `/classics/flashattention` | FlashAttention：GPU上"偷懒"的艺术，凭什么让所有大模型都离不开它？ | 2026-05-20 | 4 |
| `/classics/flashattention-2` | FlashAttention-2：GPU利用率从50%干到90%，同一个作者的自我进化 | 2026-05-23 | 4 |
| `/classics/zero` | ZeRO：把GPU显存用到极致的魔法 | 2026-05-31 | 3 |
| `/classics/instructgpt` | 1.3B打败175B：InstructGPT如何教会AI听话 | 2026-06-11 | 2 |
| `/classics/constitutional-ai` | 用AI管AI：Constitutional AI如何让大模型学会自我约束 | 2026-06-13 | 2 |

GPT-1 使用 `P3_GPT1_v1.json`，其标题与已发表记录一致；另一个版本没有代替已发表版本。BERT 有两次同标题发表记录，因此保留两个日期。DPO 本地长文尚未在现有已发表记录中匹配到，未作为公众号原稿迁入，网站现有编辑初稿仍单独标示。

## 迁移边界

- 保留原有标题、正文、章节、工程类比与原配图，不用新生成的简稿覆盖。
- 移除公众号专用的上一页/下一页提示和“回复论文”入口；由网站时间线导航接替。文章内重复的论文链接移到网站已有原文入口，GPT-1 使用既有的正确 OpenAI PDF 来源。
- 去掉微信行内样式，把视觉章节标题转成网页二级标题，以支持目录定位。31 张原图已本地化至 `site/public/papers/archive/`，不依赖微信 CDN 加载。
- 保留原图的原文图注；网站保留术语与论文来源入口，迁入状态为 `archived`，不自动标记成新一轮人工审校通过。
- 公开迁移清单 `site/content/published-archive.json` 仅包含选中的经典文章路径、标题、发表日期、原 HTML 哈希和资源路径，不导出运营数据、草稿 ID 或账号凭据。

## 复现

本地源数据不在公共 Git 中。网站构建直接读取已提交的 Markdown，不要求具备这些本地源文件。需要重新整理时：

```sh
python3 -m pip install beautifulsoup4==4.14.3 markdownify==1.2.2
python3 scripts/import_published_classics.py
# 仅在本地缺失原图时，显式使用：
python3 scripts/import_published_classics.py --fetch-images
```

脚本只迁移固定白名单且要求找到已发表记录；不会扫描后自动公开其他栏目或私人材料。首次迁移已验证所有保留的原始文字片段都出现在 Markdown 中，12 篇正文未发现片段遗漏，31 张本地图片可解码。

## 原稿后续复核事项

以下只记为维护待办，本次按用户要求保留原稿表述：

- Transformer 中“长距离依赖的彻底解决”等绝对表述，以及位置编码和多头分工的类比边界。
- GPT-1 中以 BERT 为竞争背景的回顾性叙述，需要与两篇论文的实际公开时间区分。
- FlashAttention-2 标题的 50%→90% 与论文报告的 50%—73% 指标口径不同；原稿配图与图注对应关系也需复核。论文来源：https://arxiv.org/abs/2307.08691 。
