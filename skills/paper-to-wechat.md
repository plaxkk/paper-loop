---
name: llm-paper-wechat-publish
description: 将论文原文和学习笔记转为经过审稿的公众号文章与多平台草稿
version: 3.0
---

# 论文文章生成与发布流程

在仓库根目录执行命令。所有个人署名、账号、人设、学习进度和运营数据都从本地读取，不写入公共 Skill。

## 本地配置

按 README 创建 `data/config.local.json`，或使用 `PAPER_LOOP_CONFIG` 指向本地 JSON 文件。
可通过 `pipeline.local_settings.load_local_settings()` 读取配置，但不要把整个配置打印到终端或放入模型提示词，只提取所需的非凭据字段。

- `author`：默认署名；单篇文章的 `author` 优先。
- `cover_tagline`：封面底部文字。
- `persona_file`：本地写作偏好 Markdown 文件；相对路径以仓库根目录为基准。执行此 Skill 的 Agent 必须在撰稿前读取该文件（若已配置）。Python 审稿器不会自动注入人设。
- `study_plan_file`：可选，本地学习计划；只处理用户指定或已完成学习的论文。
- `progress_file`：可选，本地进度记录。

人设、个人运营目标、社交渠道偏好与合作联系人保存在 `data/private/`，不放在示例配置中。没有配置人设时，采用清晰、克制、以论文证据为依据的中文技术写作风格。

## 工作流程

1. **读取上下文**：读取用户指定的论文原文、学习笔记，以及已配置的人设和学习进度。若 `data/weekly_strategy.json` 存在，参考其中的建议；不要把真实运营数据直接写入文章或公开文档。
2. **撰写文章**：明确论文解决的问题、此前方法的限制、具体机制和适用边界。区分论文结论与作者推断；引用数字须核对原文。不得编造实验结果。
3. **准备配图**：按需运行 `extract-figures` 和 `render-formula`；保留论文来源，检查裁剪内容及公式可读性。上传图片需要本地微信凭据。
4. **审稿**：运行 `review`，修正事实性错误，人工检查图片、链接和排版。
5. **传播适配**：按照 `distribution-loop.md` 生成各平台版本并检查效果。
6. **发布草稿**：只有用户要求发布时，才运行发布命令。不得根据学习进度自行创建定时发布任务。
7. **反馈**：按需采集后台数据，运行 `profile`、`strategy`，将结果保留在被忽略的 `data/` 内。

## 文章格式

保存在 `data/articles/`，例如：

```json
{
  "paper_id": "P1",
  "title": "文章标题",
  "digest": "文章摘要",
  "content": "<p>经过核查的文章正文</p>",
  "content_source_url": "https://arxiv.org/abs/1706.03762",
  "thumb_image": "data/covers/P1_cover.png"
}
```

省略 `author` 时，发布模块采用本地配置中的署名。需要不同署名时，在单篇 JSON 中显式设置。

## 命令

```bash
python -m pipeline.run review data/articles/article.json
python -m pipeline.run extract-figures P1
python -m pipeline.run render-formula data/articles/article.json
python -m pipeline.run distribute-adapt data/articles/article.json
python -m pipeline.run distribute-publish data/articles/article.json --dry-run
# 用户要求发布后执行：
python -m pipeline.run publish data/articles/article.json
python -m pipeline.run profile
python -m pipeline.run strategy
```

`review` 使用本地 `llm` 配置或其指定的环境变量。不要读取或执行用户的 shell 配置来查找密钥。
