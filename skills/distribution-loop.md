---
name: paper-distribution-loop
description: 论文解读文章的传播闭环：截图级判断+内链网络+多平台自动分发。每篇文章强制执行。
version: 2.0
---

# 论文文章传播闭环

## 背景

kk 的公众号内容方向按大模型发展史顺序解读论文，话题不可跳选。53粉阶段自然流量天花板约 160
阅读/篇，且 kk 不在朋友圈转发（形象顾虑）。传播策略围绕三条不依赖社交图谱的杠杆:

1. **截图级判断句** — 提高转发率（读者看到打动他的判断→截图发群）
2. **文章间内链网络** — 提高系列曝光（新读者搜到一篇→被引到全系列）
3. **多平台自动分发** — 提高搜索流量（知乎/掘金/CSDN 长尾流量注入）

## 触发条件

每篇文章写完（Step 1 撰文完成后）、发布前（Step 5 发布前），执行以下全部步骤。
skill `llm-paper-wechat-publish` 的 Step 5.5 引用此规范。

---

## 强制步骤

### Step A: 植入截图级判断句

在核心洞察讲完后、「写在最后」之前，插入深色背景加粗判断句。

HTML:
```html
<p style="margin: 28px 0 20px; padding: 16px 18px;
   background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
   border-radius: 6px; text-align: center; line-height: 1.8;">
  <strong style="font-size: 16px; color: #e0e0e0; letter-spacing: 0.5px;">
  {判断句}
  </strong>
</p>
```

**判断句标准:**
- 一句话，读完想截图发群里
- 不是总结（「本文讲了X、Y、Z」），是判断（「X 不是 Y，而是 Z」）
- 有锋芒但不偏激
- 无 AI 痕迹 — 没有「值得注意的是」「这说明了一个道理」
- 跟论文核心贡献直接相关

**典型句式:** 「X 真正的价值不是……而是……」「X 和 Y 是两回事」「最快的 X 是不发生的 X」「不是 X 变大了，是你终于不再……」

**自检:** 把这句话单独拿出来发给工程师朋友。他会回复「确实」还是沉默？

### Step B: 构建内链网络

**B1. 文首上下文标记**

封面图后、第一段前:
```html
<p style="margin: 0 0 12px 0; font-size: 13px; color: #999;">
📖 大模型论文学习笔记 · {阶段名} · 第{N}篇</p>
```

阶段: P1-P5=阶段一(Transformer与预训练) P6-P10=阶段二(训练与扩展) P11+=阶段三(对齐与人类反馈)

**B2. 文末导航**

论文链接 footer 之前:
```html
<div style="margin: 28px 0 8px; padding: 14px 0;
   border-top: 1px solid #eee; border-bottom: 1px solid #eee;
   display: flex; justify-content: space-between; font-size: 14px; color: #666;">
  <span>← <span style="color: #576b95;">上一篇：{标题截断25字}</span></span>
  <span><span style="color: #576b95;">下一篇：{标题截断25字} →</span></span>
</div>
<p style="margin: 4px 0 16px; font-size: 12px; color: #aaa; text-align: center;">
📚 在公众号内回复「论文」查看全系列目录</p>
```

微信不支持外部超链接，导航用纯文本。知乎/掘金/CSDN 版本改为 `<a>` 超链接（这些平台支持）。

### Step C: 多平台自动分发

#### C1. 首次配置（仅一次）

```bash
# 登录各平台（浏览器打开→手动登录→自动检测保存）
python -m pipeline.run distribute-login           # 所有平台
python -m pipeline.run distribute-login --zhihu   # 仅知乎
python -m pipeline.run distribute-login --juejin  # 仅掘金
```

登录态保存到 `~/.paper-to-wechat/browser_states/{platform}_state.json`。系统每 3 秒主动检测登录成功（URL 不含 login/signin = 已登录），不再盲等超时。

#### C2. 每次发布

```bash
# 预览各平台适配版本
python -m pipeline.run distribute-adapt articles/P14_KTO.json

# dry-run（打开编辑器填内容但不点发布）
python -m pipeline.run distribute-publish articles/P14_KTO.json --dry-run

# 正式发布
python -m pipeline.run distribute-publish articles/P14_KTO.json

# 仅发布特定平台
python -m pipeline.run distribute-publish articles/P14_KTO.json --zhihu
python -m pipeline.run distribute-publish articles/P14_KTO.json --juejin
```

#### C3. 代码架构

```
modules/distribution/
├── adapters.py              # WeChat HTML → 知乎/掘金/CSDN Markdown
├── orchestrator.py          # 多平台编排：adapt → publish all
└── platforms/
    ├── base_publisher.py    # Playwright 基类（登录态持久化+主动检测）
    ├── zhihu_publisher.py   # 搜问题 + 相关度过滤 + 发答案
    └── juejin_publisher.py  # 开编辑器 + 填内容 + 发布

知乎搜问题为全自动流程（三步）:
  1. `generate_search_query(article_json)` — 从标题/digest 自动提取技术术语生成搜索词。
     新论文零配置。已知论文通过 ZHIHU_SEARCH_QUERIES 字典手动覆盖优化。
  2. `search_questions(query)` — 知乎搜索，仅保留 /question/ 类型 URL（排除专栏文章）。
  3. `_filter_relevant(questions)` — 关键词加权评分筛选，低于阈值 0.10 跳过。
     技术术语（DPO/KTO 等）×3 权重，中文二元组 ×1 权重。

完整知乎答案草稿: `data/reports/zhihu-q-and-a-drafts.md`

---

## 发布后检查清单

- [ ] 截图判断句在手机上显示正常（深色背景+白色文字，16px）
- [ ] 文首上下文标记显示正常（13px 灰色）
- [ ] 文末导航链接显示正常
- [ ] 知乎/掘金已发布（distribute-publish 返回 success + URL）
- [ ] 知乎答案版本含 `<a>` 超链接（非纯文本）
- [ ] 公众号「论文」自动回复已配置（后台手动操作 — 暂无 API）

---

## 已知限制

- **CSDN**: 无公开 API，Playwright 可行性未知。kk 手动同步。
- **公众号自动回复**: 微信后台无设置 API，需手动配置。
- **登录态过期**: cookie 过期后重跑 `distribute-login`。
- **知乎搜索已实现通用化**: 搜索词从文章 JSON 自动生成（提取英文缩写+中文关键词），
  无需为每篇论文手动配置 ZHIHU_SEARCH_QUERIES。已知论文可手动覆盖以获得更优搜索词。
  `_filter_relevant()` 对每个问题做加权评分筛选（技术术语×3 + 中文二元组×1），
  低于阈值 0.10 自动跳过，不强行回答不相关问题。
- **掘金 Markdown 模式**: 当前 fallback 到富文本。Markdown 切换按钮选择器未命中，需补充 bytemd 组件的具体 class。
- **爆款预测不能靠 9 篇文章**: 见 `llm-paper-wechat-publish` Step 0 策略可信度判断。

---

## 实现时的坑

### Playwright 登录检测

1. **弹窗式登录 ≠ URL 变化**: 掘金等平台的登录是弹窗 modal，URL 始终是首页。默认的 URL 检测（不含 login/signin）会产生假阳性 → 用户还没输手机号就判定为已登录 → 保存空状态 → 关闭浏览器。解决: 平台子类覆盖 `_check_logged_in()`，检查 DOM 中是否有登录后才出现的元素（如用户头像 `.avatar`），且登录按钮不可见。

2. **知乎 header 固定栏遮挡按钮**: 知乎有 header 和 main 两个「写回答」按钮。`.first` 取到 header 中的按钮 → `header role="banner" intercepts pointer events` → 点击超时。解决: 用 `main button:has-text("写回答")` 锁定 main 区域内的按钮，或 fallback `.last`。

3. **Strict mode 多元素匹配**: `page.locator('button:has-text("写回答")')` 匹配多个元素时 Playwright strict mode 报错。解决: 始终加 `.first`/`.last`/`.nth()` 或限定父容器（如 `main button:...`）。

### 代码生成陷阱

4. **`execute_code` 的 `write_file` 行号污染**: `read_file` 返回 `1|#!/usr/bin/...` 格式（行号前缀），`write_file` 原样写入 → 文件第一行变成 `1|#!/usr/bin/env python3` → SyntaxError。修文件用 `patch` 或 `terminal`，不要用 `execute_code` 的 `write_file` 写已有文件。

5. **f-string 真实换行**: 通过 `write_file` 写 Python 源码时，`print(f"\n{...}")` 可能被解释为真实换行插入源码 → SyntaxError。改用 `print(f"\\n{...}")` 或 `print()` 单独一行。

6. **`input()` 在非 TTY 环境**: `terminal()` 没有标准输入 → `input()` 抛 `EOFError`。登录流程用主动轮询代替等待用户按键。

---

## 更新指南

- 发现判断句句式有效/无效 → 更新 Step A
- 新增论文 → 更新 SERIES 列表（内链导航 + 判断句注入）。搜索词自动生成，无需手动配置。
- 搜索词不够好 → 在 ZHIHU_SEARCH_QUERIES 添加手动覆盖（可选，已知论文已有 P1-P13 预设）。
- 新增分发平台 → 添加 publisher 类 + 更新 orchestrator
- 登录检测对新平台失效 → 覆盖 `_check_logged_in()`
- 知乎编辑器 UI 变动 → 检查 `post_answer()` 中的按钮和编辑器选择器
