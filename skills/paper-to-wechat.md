---
name: llm-paper-wechat-publish
description: 将kk的大模型论文学习笔记生成微信公众号文章的完整流程
version: 2.5
---

# 公众号论文文章生成与发布流程

## 概述

将 kk 的论文学习笔记转化为微信公众号文章，按学习计划的阶段划分撰写。
- 项目路径: `~/hermes-data/llm-paper-plan/`
- 学习计划: `README.md`（6阶段45篇论文）
- 进度跟踪: `progress.md`
- 微信工具: `wechat/` 目录下

## 阶段划分（严格遵守）

- 阶段一 P1-P5: Transformer + 预训练（Attention, BERT, GPT-1, GPT-2, GPT-3）
- 阶段二 P6-P10: Scaling Laws, Chinchilla, FlashAttention, MoE, LLaMA
- 每阶段写完后可以写一篇阶段总结

只写当前阶段已学习完的论文，不提前写后续阶段的内容。

## 阶段总结文章

每阶段完成后可写一篇总结文章，将5篇论文串成一条叙事线。

JSON 格式：
```json
{
  "paper_id": "stage2_summary",
  "type": "stage_summary",
  "title": "吸引人的标题",
  "author": "kk",
  "digest": "120字以内的摘要",
  "content": "HTML内容",
  "content_source_url": "",
  "thumb_image": "images/covers/stage2_summary_cover.png"
}
```

footer 格式（无论文链接）：
```html
<p style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #eee; font-size: 13px; color: #999;">kk的大模型论文学习笔记 · 阶段二总结 · 训练与扩展</p>
```

写作要求：用一条叙事线（如高速公路建设、摩天大楼）把5篇论文串起来，不要逐篇罗列。

## 批量生成技巧

用 delegate_task 子代理并行写多篇文章效率很高。给子代理的 prompt 必须包含：
1. 完整 JSON 结构模板
2. 精确的 HTML 开头/包裹/结尾格式
3. FORBIDDEN 列表（blockquote、emoji前缀、对入门者的启示、编号要点）
4. 论文核心内容要点（before/after定位、核心贡献、关键数字）

子代理不需要读已有文章做格式参考——只要 prompt 里格式要求足够精确即可。

## 完整流程（6步）

### Step 0: 读取数据飞轮（撰文前必做）

在开始撰写任何文章前，必须先检查是否存在数据飞轮策略文件：

```
read_file /Users/kk/hermes-data/llm-paper-plan/wechat/data/weekly_strategy.json
```

如果文件存在且 `raw_stats.total_articles >= 3`，说明有足够数据支撑。在撰写文章时，必须将以下策略洞察融入写作决策：

1. **话题选择**：优先选择 `writing_strategy.recommended_topics` 中列出的方向
2. **标题风格**：遵循 `writing_strategy.title_style` 中的建议（如「冒号式」「疑问句」）
3. **发布时间**：参考 `writing_strategy.publish_timing`
4. **内容侧重**：高阅读文章的共同特征（工程向、算力优化、类比贴工程师日常）在写作时优先复现
5. **读者画像**：`raw_stats` 中的粉丝数、均篇阅读量决定了文章深度和广度的分寸——粉丝基数小时，每篇都需要有「转发价值」来破圈

如果文件不存在或数据不足，跳过此步，按常规流程撰写。

由阿飞根据 kk 的学习笔记和论文原文，用通俗易懂的公众号风格撰写。

文章 JSON 格式：
```json
{
  "paper_id": "P1",
  "type": "paper",
  "title": "吸引人的标题",
  "author": "kk",
  "digest": "120字以内的摘要",
  "content": "<section>HTML内容</section>",
  "content_source_url": "",
  "thumb_image": "images/covers/P1_cover.png"
}
```

文章风格要求：
- 标题：吸引眼球但不夸张
- 正文：通俗易懂，用比喻解释技术概念
- 结构：开头引子 → 核心问题 → 方法解读 → 关键发现 → 收尾
- 在正文中融入论文的关键图片（架构图、实验图等），用 figure 标签包裹，带 figcaption 说明来源

**写作哲学：kk 的公众号不是论文翻译站，是一个工程师用自己的方式理解 AI 的记录。**

目标读者是工程侧同学，他们不需要看懂所有公式，但读完必须"有收获"。收获不只是知识，还有认知上的触动——一篇好文章应该让读者放下手机后还在想刚才读到的那个观点。

---

**〇、后端工程师可读性准则：DL 术语不能当已知概念**

目标读者是工程侧同学（前端/后端/全栈），DL（深度学习）领域的术语对他们来说不是 common sense。以下术语在首次出现时必须给一行简短解释：

| 术语 | 解释模板 |
|------|----------|
| **fp16 / fp32** | fp16 = 16 位半精度浮点数（每个数 2 字节，精度低但够用）；fp32 = 32 位单精度浮点数（每个数 4 字节，精度高）。模型参数用 fp16 省显存，优化器状态必须用 fp32 防精度丢失。 |
| **混合精度训练** | 前向和反向传播用 fp16 计算（快、省显存），参数更新时用 fp32 确保精度。 |
| **Ψ (Psi)** | 原论文中表示"参数量大小"的符号——1Ψ = 模型参数本身的 fp16 存储量。以 10 亿参数为例，1Ψ = 2GB。文中首次出现时必须定义。 |
| **all-gather** | 所有 GPU 各拿出一块数据，广播拼接，最终每张卡都拿到完整结果。首次出现时加括号注释。 |
| **reduce-scatter** | 反向操作：各 GPU 把数据汇总（reduce）后再切分（scatter），最终每张卡只拿自己负责的那一片。 |
| **动量 m / 自适应学习率 v** | 用通俗名称（"动量""自适应学习率"）为主，数学名（"一阶矩估计""二阶矩估计"）降为括号注释或直接省略。 |
| **mini-batch** | 训练时把一整批数据拆成多个小批次，每张 GPU 领一个小批次独立计算。首次出现时加一句说明。 |
| **前向传播 / 反向传播** | 前向 = 数据从输入到输出算一遍（预测）；反向 = 从输出到输入算梯度（学习）。如果上下文已有 P6-P7 的积累可以不说，但首次遇到时必须提。 |

**原则：宁可多写一行注释，不要让读者因一个陌生词卡住整段。** 后端人遇到不认识的符号不会自己去搜——他们要么跳过整段，要么关掉文章。

---

**一、文章结构：技术正文 + 点缀式穿插 + 观点收尾**

文章主体是扎实的技术讲解（保持原版风格，通俗易懂、逻辑清晰）。不在正文中大段输出观点，而是通过两个手段注入 kk 的声音：

**手段 A：灰色斜体旁注（inline aside）**

在关键技术段落末尾，用灰色斜体（`<em style="color: #888; font-size: 13px;">`）插入一句简短的洞察或类比。每篇 3-5 处，每处 1-2 句话。作用是让读者在学知识的同时感受到"有人在带我看"。

旁注的几种类型：
- 工程类比："做后端的同学一定很熟悉这个模式——数据库引擎是通用的，不同的业务只是在上层接不同的API"
- 技术洞察："BERT做的是判断题，GPT-1做的是创作题。创作题更难，但能力上限远高于判断题"
- 演进脉络："站在今天看，这就是prompt engineering的雏形——GPT-1要手动设计格式，GPT-2去掉了微调，GPT-3给几个例子就行"
- 真实困惑："为什么要故意少看信息？因为生成天然是单向的"

**手段 B：结尾「写在最后」段落**

技术内容全部讲完后，用 `<hr>` 分隔线隔开，加一个「写在最后」小节，3-5 段。这里集中输出：
- kk 的个人判断和思考（INTJ 式的理性洞察）
- AI 平权 / 技术普惠的价值观
- 真实的学习感受

结尾不要总结全文，而是留一个值得琢磨的想法。

---

**二、写作人设：INTJ 的锋芒 + 内在的温度**

文字整体是理性克制的 INTJ 风格——独立思考、直击本质、不人云亦云。但在理性之下有一层柔软：相信技术的力量应该让每个人受益，相信好奇心是工程师最珍贵的品质，相信自由平等和 AI 平权。

这个组合很自然：INTJ 喜欢钻透本质，而 AI 平权的本质就是让技术不再被少数人垄断——这本身就是一个值得深挖的洞察。不需要刻意抒情，真实的理性洞察本身就带着温度。

**语气示范（旁注级别，不是大段）：**
- "GPT-1选的不是「少看」，而是「按生成的方式看」"
- "信念在验证之前叫冒险，验证之后才叫远见"
- "FlashAttention 让我想到一个朴素的道理：最快的 I/O 是不发生的 I/O"

---

**三、观点要有锋芒，但要克制**

旁注和结尾里的观点要具体、有锋芒、能引发讨论。

**好观点的标准：**
- 振聋发聩：打破读者的默认认知。"BERT 赢了当下，GPT 赢了未来"
- 一针见血：一句话说透本质。"Transformer 的核心创新不是 attention，而是让序列建模变成了可并行的矩阵运算"
- 有技术支撑：不是空谈，观点要站得住
- 可讨论：好观点让人想反驳或补充

**分寸：**
- 自信但不傲慢——"我觉得"比"众所周知"好
- 有态度但不偏激——可以说"这个设计很巧妙"，但不要无脑吹或黑
- 口语化但有节奏——像跟同事聊天，不是写论文摘要
- 没有AI痕迹——禁止"值得一提的是"、"总而言之"、"综上所述"

---

## 公众号写作人格与价值观补充规范（保持风格连续，不要像换了一个人）

这部分规范的目标，不是把文章改写成另一种腔调，而是在**不破坏 kk 既有表达习惯**的前提下，补强文章的人设稳定性、信任感、价值观与观点锋芒。

**最高原则：风格连续性优先。**

读者应该感觉这是同一个人写得越来越稳、越来越透，而不是某一天突然切换成另一种人格。新增的人设表达必须是**在原有风格里的自然加深**，不是另起炉灶。

### 一、保持连续性的写作原则

- 不刻意改变原有句式节奏、段落组织方式和技术讲解主干
- 不突然增加大量抒情、自白、情绪化表达
- 不突然变成“人生感悟型”或“鸡汤观点型”公众号
- 不为了显得真实而刻意示弱、卖困惑、卖焦虑
- 不为了显得有思想而堆砌抽象大词、空洞判断

允许升级的，是下面这些东西：
- 观点更准一点
- 判断更深一点
- 过渡更自然一点
- 对读者更有帮助一点
- 结尾更有余味一点

也就是说，**是同一个人继续往前走，不是换一个人来写。**

### 二、人设定位：不是小白陪跑，也不是全知导师

这个号的人设应保持为：
**一个有工程思维、尊重事实、愿意下笨功夫把技术问题想透的写作者。**

不是“我什么都懂”，也不是“我什么都不懂陪你一起学”，而是：
- 我会认真拆问题
- 我会区分事实、判断和猜测
- 我不会把没想透的东西硬写成结论
- 我输出内容，是为了让读者真正获得更好的理解框架

这种可信感不是靠故作谦虚，而是靠稳定、克制、准确。

### 三、真实感的来源：来自判断形成过程，不来自浅白示弱

真实感要有，但不能把文章写得像入门陪伴笔记。

优先写这三类真实感：

1. **误区识别**
   - “这篇最容易被误读的地方是……”
   - “如果只看表面，很容易把它理解成……但真正关键的是……”
   - “第一次接触这个问题时，人很容易把注意力放错位置……”

2. **判断形成过程**
   - “我后来才意识到，这篇论文真正重要的不是……而是……”
   - “如果把它放回当时的技术约束里看，它的分量会比表面大得多……”
   - “这篇论文表面像是在优化局部，实际上改的是系统瓶颈的位置……”

3. **工程体感/第一性原理体感**
   - “从工程视角看，这更像是在处理……”
   - “它真正碰到的不是算法花样问题，而是资源约束问题……”
   - “很多性能问题表面在算力，底层其实卡在数据搬运/系统调度/内存层级……”

少写这类表达：
- “这个好难，我看了很久才懂”
- “我也不太懂，但我感觉……”
- “大家不用怕，其实很简单”

这些话虽然显得亲近，但会削弱文章的密度和可信度。

### 四、利他不等于降智，通俗不等于浅薄

文章要帮助读者降低理解成本，但**不能通过牺牲思想密度来换取表面易懂**。

写作目标应是：
- 压缩复杂度，而不是削平复杂度
- 讲清楚，而不是讲幼稚
- 让读者觉得“原来是这样”，而不是“这也太简单了”

目标读者不是算法研究员，但也不是需要被哄着读的人。应把读者默认成：
**有理解能力、但没有足够时间自己啃原文的工程侧同学。**

因此，表达方式应保持：
- 语言尽量清楚
- 逻辑必须完整
- 判断要有分量
- 不故作高深，也不刻意降智

### 五、观点风格：冷静、锋利、一针见血，但不要像另一个人

可以有观点，而且应该有观点。但观点必须建立在原文、实验结果、历史脉络或系统约束之上。

好的观点通常满足：
- 不是复述摘要，而是指出核心矛盾
- 不是情绪表态，而是结构性判断
- 不是为了犀利而犀利，而是因为看透后只能这么说

适合的观点句式：
- “真正重要的，不是……而是……”
- “表面上看它解决的是 A，实际上它改写的是 B。”
- “这篇论文的分量，不在于把指标再抬高一点，而在于它改变了后续系统设计默认相信的东西。”
- “很多人讨论的是结果，但这篇真正动到的是约束条件。”

不适合的写法：
- 夸张断言
- 强行金句
- 密集输出像短视频文案一样的“炸裂观点”
- 突然变得咄咄逼人、姿态过满

记住：**锋利感应该像刀刃藏在逻辑里，而不是挂在表面语气上。**

### 六、第一性原理写法：往约束条件下钻，而不是空谈本质

所谓第一性原理，不是频繁说“本质上”，而是能往下追问：
- 这篇论文表面在解决什么问题？
- 真正卡住它的约束是什么？
- 作者改动了系统中的哪条关键因果链？
- 为什么这个改动会带来后续连锁反应？

如果一篇文章能稳定回答这四个问题，思想密度自然会上去，而不用故意装深刻。

尤其适合 kk 的表达方式是：
- 把方法放回历史脉络里看
- 把性能放回系统瓶颈里看
- 把论文贡献放回 before/after 的变化里看

### 七、价值观表达：要稳定存在，但以“渗透”而不是“宣讲”的方式出现

公众号应持续传递这些价值观：
- 尊重事实
- 反炫技
- 反信息泡沫
- 利他
- 技术普惠 / AI 平权

但这些价值观不应该每篇都被大声喊出来，而应通过以下方式自然渗透：
- 认真区分事实与判断
- 不拿术语制造门槛
- 不把复杂问题包装成廉价结论
- 在结尾处留下一个更值得思考的判断，而不是制造情绪高潮
- 让读者感受到：写这篇文章是为了帮助理解，不是为了展示优越感

### 八、结尾“写在最后”升级原则：余味更强，但腔调别突变

“写在最后”依然保留，但不要突然写成抒情散文。

更合适的结尾方向：
1. 对技术路线的判断
2. 对历史位置的重新定位
3. 对工程实践意义的提炼
4. 对技术普惠/理解门槛的克制表达

结尾应该让人觉得：
“这个作者把问题又往下想了一层。”
而不是：
“作者忽然开始讲人生了。”

### 九、禁止事项（为了防止风格跑偏）

- 禁止把“真诚”写成“示弱”
- 禁止把“通俗”写成“浅白”
- 禁止把“观点”写成“情绪输出”
- 禁止把“锋利”写成“故作深刻”
- 禁止把“共鸣”写成“套路化自我暴露”
- 禁止突然使用与既有文章明显不一致的文风（例如过度文艺、过度社评、过度鸡汤）
- 禁止编造个人经历、项目经验或情绪故事来制造真实感

### 十、发布前新增自检清单（人格与风格）

- [ ] 这篇文章整体气质是否与前文保持连续，没有“像换了个人写”的突兀感
- [ ] 是否在不改变主干风格的前提下，补强了判断力、真实感和价值观
- [ ] 是否至少有 1-2 处体现“误区识别 / 判断形成 / 工程体感”的表达
- [ ] 是否避免了浅白陪跑式表达
- [ ] 是否避免了空洞的大词和故作深刻
- [ ] 是否区分了事实、分析、判断、猜测
- [ ] 结尾是否有余味，但没有突然切换成抒情号口吻
- [ ] 读者读完后记住的应是“问题被讲透了”，而不是“作者在塑造人设”

### 十一、AI 痕迹识别与自检

AI 撰文有一些高频模式，必须在发布前检查并清除。以下每一条都是经过实际 S2 文章审稿验证过的真实案例。

**识别规则（按严重度排序）：**

| # | AI 痕迹 | 例子 | 人怎么写 |
|---|---------|------|----------|
| 1 | **闭幕词式结尾句** | “路还长，但至少我们已经知道……” “未来已来，让我们……” | 用一个具体的工程师判断或困惑收尾，而非展望式金句 |
| 2 | **“这个故事/这个案例说明了一个道理”** | “它说明了一个道理：在系统优化里……” | “FlashAttention-2 让我想到一句话：最快的 I/O 是不发生的 I/O。” ——直接写判断，不要用“这说明了X”做说教包装 |
| 3 | **英文直译的连接词** | “现在退后一步”（now step back）、“值得注意的是”（it's worth noting） | “回头看这五篇”、“串起来看” |
| 4 | **PPT 式逐条罗列** | 用 bold 人名 + 统一句式（“XX告诉你/纠正了/解决了”）逐一排列 | 用叙事段落串联，让论文之间的关系自然流动，不制造 bullet-point 节奏 |
| 5 | **排比式展望句** | “新的能力开始涌现，新的训练方法也应运而生”（三个“新的”） | 用具体的下一站内容做过渡：“阶段三要讲的是 RLHF、DPO 这些东西——也就是 ChatGPT 能‘听懂人话’的幕后功夫” |
| 6 | **“应运而生”及相关成语** | 应运而生、层出不穷、方兴未艾、蔚然成风 | 全部禁止。这些是 AI 最爱的四字填充，没有信息量 |

**自检清单（发布前逐项确认）：**

- [ ] 结尾句是具体的判断/困惑/问题，而非“路还长”“未来可期”式展望
- [ ] 没有任何“它说明了一个道理”“这个故事告诉我们”式说教
- [ ] 没有“现在退后一步”“值得注意的是”“综上所述”等 AI 连接词
- [ ] 汇总段落是叙事流而非 bullet point 罗列
- [ ] 没有排比式展望句（连续多个“新的”）
- [ ] 没有“应运而生”“层出不穷”等 AI 高频四字成语
- [ ] 段落过渡用论文间的因果关系自然衔接，而非“接下来我们看下一篇”



### 十二、工程共鸣原则：让工程师点头的洞察（基于 P11 实际审稿反馈提炼）

这篇文章的目标读者是工程师，而工程师看文章有一个特点：**他们不满足于「懂了」，他们要的是「原来如此」——那种被一句话捅破窗户纸的瞬间。** Claude 对 P11 的评审指出了差距：文章「讲清楚了」，但还没到「一针见血、让人拍桌子」的层次。以下规则提炼自这次评审，目标是让每篇文章都至少有一到两处让工程师点头的洞察。

**十二-A、类比必须从工程师的日常出发，不是从学习者视角出发**

❌ 学习者视角：「就像一个家教手把手演示正确答案」
✅ 工程师视角：「预训练是通识教育，SFT 是 onboarding。一个清华毕业的新人代码能力很强，但写出来的东西在 review 里过不了——因为他不知道这个团队的约定。GPT-3 就是这个新人。」

原则：
- 能用工位/代码review/上线/API/缓存/数据库/分布式系统做比方的，不用教学场景做比方
- 工程师的共鸣点在「契约」「接口」「成本」「瓶颈」「解耦」，选这些词作为类比锚点
- 每篇文章至少有一处类比让读者想转发给同事说「你看这个比喻」

**十二-B、每个核心技术决策，必须追问一句「工程上为什么聪明」**

工程师尊重的是「在约束下找到优雅解」。文章不能只描述「做了什么」，必须解释「为什么这个做法在工程上是聪明的」。

❌「InstructGPT 训练了一个 Reward Model 来替代人类打分」
✅「人类标注是线性成本，Reward Model 是一次性摊销。这是整个设计真正聪明的地方——它把稀缺资源（人类判断力）蒸馏成了可以无限次调用的函数。做过分布式系统的工程师应该很熟悉这个模式：你不可能每次请求都查主库，所以你做缓存。」

关键追问模板：
- 这个设计省了什么？（人力？算力？时间？）
- 这种省钱方式有什么工程上的类比？（缓存、连接池、索引、懒加载）
- 为什么不能更简单地解决？（反事实：如果不用这个方法会怎样）

**十二-C、「解耦」是工程师最敏感的神经——碰到就要放大**

工程师最兴奋的时刻之一，就是发现两个原本被认为绑定的东西其实可以分开。如果论文的核心贡献是解耦，必须在文章中显式命名这种解耦。

❌「1.3B 打败 175B，说明对齐比规模更重要」
✅「InstructGPT 证明了一件反直觉的事：模型能力和模型可用性是两个维度，两者可以解耦。预训练负责能力，对齐负责可用性。这就好比一个 API 的性能和它的接口设计是两回事——你可以有一个极其高性能但接口设计极烂的服务，它在生产环境里一样没法用。」

识别解耦的技巧：
- 论文是否分开了两个原本混为一谈的概念？（能力 vs 可用性、性能 vs 接口设计）
- 论文是否证明某件事不需要依赖另一件事？（小模型+好的对齐 > 大模型+差的对齐）
- 如果是，必须用一句「X 和 Y 是两回事」来收束

**十二-D、核心论点必须前置，不能在第三段才出现**

工程师的阅读耐心有限。全文最重要的那句话——就是那个看完文章以后读者会记住的 insight——必须出现在开头引子部分，而不是藏在第三段。

如果文章的核心信息是「从「能生成」到「能被使用」中间有一道工程鸿沟」，这句话或者它的变体必须在文章前 3 段内出现。

❌ 结构：第一段问题引入 → 第二段继续铺垫 → 第三段才亮出核心判断
✅ 结构：第一段直接亮出核心判断 → 第二段展开为什么这是一个问题 → 第三段讲怎么解决

自检：读者看完前三段，能不能用一句话复述这篇文章在讲什么？如果不能，核心论点没有前置。

**十二-E、结尾不要流水账，要 punch line**

「此后 xxx 都在用 RLHF」是流水账。「InstructGPT 解决的不是模型变聪明的问题，而是聪明的模型变得能被使用的问题。一个不能被有效使用的技术，等于不存在」是 punch line。

结尾的「写在最后」应该做两件事之一：
1. **重新框定问题**：告诉读者「这篇文章真正在讲的其实是这个」，给一个新的视角
2. **留下一个值得琢磨的判断**：不是感慨，不是展望，是一个具体的、可辩论的判断

❌ 「RLHF 成为了行业标准，后续的 ChatGPT、Claude 都在用这个技术栈」
✅ 「从某种意义上说，InstructGPT 解决的不是「模型变聪明」的问题，而是「聪明的模型变得能被使用」的问题。这个区别，比它听起来重要得多。一个不能被有效使用的技术，等于不存在。」

**十二-F、发布前新增自检（工程共鸣）**

- [ ] 是否至少有一处工程类比来自工位/代码review/上线/API/缓存/分布式系统（而非教学/学习场景）
- [ ] 是否至少有一处追问了「工程上为什么聪明」（而非仅描述「做了什么」）
- [ ] 如果有解耦型发现，是否显式命名了这种解耦
- [ ] 核心论点是否在前 3 段内出现（而非藏在第 3-4 段）
- [ ] 结尾是否给出了 punch line 而非流水账
- [ ] 是否有一处类比能让读者想转发给同事

### 十三、实操穿透：不能只讲 what 和 why，必须讲 how

what 和 why 让读者「懂了」，how 让读者「会了」。面向工程师的文章，如果只停在概念层，读完之后的感觉是「道理我懂了，但我还是不知道怎么做的」。需要把论文的核心实现方法穿插进叙事，让读者既理解思想，也看得见落地。

**十三-A、how 的三层穿透**

每篇文章的核心技术部分，至少要穿透以下三层中的至少两层：

1. **训练怎么跑的**：数据怎么来的、损失函数长什么样、优化器怎么选的、训练了几个 epoch、batch size 多少。这些数字不是凑字数——工程师看到具体的参数配置，才能判断这个方法的工程可行性和成本。

2. **关键公式/算法用文字讲一遍**：不需要列完整数学推导，但核心的损失函数或算法步骤必须用大白话走一遍。比如「Reward Model 的训练目标是：给定同一个 prompt 的两个回答，让好的那个得分尽量高于差的那个。用 Bradley-Terry 模型把这个偏好概率化，然后用交叉熵来优化。」

3. **为什么要这样实现而不是那样**：这是 how 层最有价值的部分——不只说「做了什么」，还解释「为什么这样做而不是那样做」。比如 PPO 为什么加 KL 约束？因为不加的话模型会 exploit reward model 的漏洞（reward hacking），生成一些高分但毫无意义的文本。

**十三-B、how 的穿插方式——不另起炉灶，缝在叙事里**

❌ 错误做法：讲完概念后单独开一个「技术实现细节」小节，罗列公式和参数。读起来像教科书，工程师也会跳过去。
✅ 正确做法：在讲每一步的时候，自然地把实现细节缝进去。

示例（P11 Step 2 的改写）：

> 具体流程：给 SFT 模型一个 prompt，生成 K 个不同回答（论文用 K=4~9），让标注员排序。然后训练 Reward Model——输入是 (prompt, answer)，输出一个标量分数。
>
> RM 的损失函数很直观：对每一对排序 (A > B)，让 A 的得分减去 B 的得分尽可能大。形式化地写就是 Bradley-Terry 模型的负对数似然——你把它理解成「让好的回答和差的回答在分数上拉开距离」就行。这个 RM 用 GPT-3 6B 初始化，去掉最后的语言模型头，换成一个输出标量的线性层，在比较数据上微调。
>
> 为什么是 6B？论文试过更大的 RM，发现收益递减，而且 6B 在推理时不会成为瓶颈。这个选择本身就是工程取舍——够用就好，不追求最优。

关键：how 不是独立段落，而是在讲「第二步做了什么」的时候自然展开的附加信息。读者感觉不到在「学实现细节」，而是在理解设计逻辑。

**十三-C、什么情况下 how 可以少讲**

并非每个技术点都需要展开 how。以下情况可以简略带过：
- 该技术不是论文的核心贡献（如用了标准的 Adam 优化器，不需要解释 Adam 原理）
- 工程细节和核心洞察无关（如具体的 GPU 型号、训练用了几天）
- 过于琐碎的消融实验参数

判断标准：**如果去掉这个 how，读者对核心贡献的理解会不会残缺？** 如果会，必须讲。

**十三-D、发布前 how 层自检**

- [ ] 核心方法部分：是否走了一遍「数据→训练目标→优化方式」的链路
- [ ] 是否至少有一个关键参数被具体提到（如 K=4~9、RM=6B、PPO batch=512）
- [ ] 是否有至少一处解释了「为什么这样实现而不是那样」
- [ ] how 信息是否缝在叙事里，而非单独罗列

> 具体改写示例见 `references/how-layer-before-after.md`（P11 PPO 段落的前后对比）

### 十四、中文措辞：按中国人的说话习惯写，不按英文直译

面向中文读者的技术文章，措辞必须符合中文语境下的自然表达。AI 生成的文本经常出现「英式中文」——语法正确但读起来别扭，因为思维路径是英文直译。

**十四-A、禁用词清单（英式中文高频词）**

| 别扭写法 | 问题 | 改为 |
|---------|------|------|
| code review的礼仪 | 「礼仪」太正式，像外交礼节 | code review的规矩/规范 |
| 值得注意的是 | It's worth noting 的直译 | 删掉，直接说内容 |
| 现在退后一步 | now step back 的直译 | 回头看 / 串起来看 |
| 这说明了一个道理 | this tells us a lesson 的直译 | 删掉，直接下判断 |
| 退一步讲 | 英文让步结构的直译 | 换句话说 / 或者换个角度看 |
| 在某种意义上 | in a sense 的直译 | 具体说「从工程的角度看」/「从产品的角度看」 |
| 甜点 | sweet spot 的直译，中文不这么用 | 最佳平衡点 / 刚刚好 |
| 本质上 | essentially 的直译 | 具体说哪里本质，不要用这个词当万能前缀 |

**十四-B、措辞自检方法**

写完一段后，在心里用口语读一遍。如果读起来像翻译腔（比如你会对同事说「code review的礼仪」吗？），就换掉。

原则：
- 工程师之间怎么聊技术，文章里就怎么写
- 宁可口语化一点，不要书面化到不自然
- 「规矩」「规范」「约定」「门道」比「礼仪」「准则」「范式」更自然
- 长句拆短句，中文不习惯多层嵌套从句

**十四-C、发布前措辞自检**

- [ ] 读一遍全文，是否有任何地方读起来像翻译腔
- [ ] 是否用了「值得注意的是」「退一步讲」等英文直译连接词
- [ ] 技术术语的中文表达是否自然（如「规矩」而非「礼仪」）

---

1. **文首封面图**：文章 HTML 最开头必须有文首封面图（上传到微信 CDN 后引用）：
```html
<figure style="margin: 0 0 16px 0; text-align: center;">
  <img src="{CDN_URL}" style="width: 100%; display: block;" alt="封面">
</figure>
```
文首封面图来源：`wechat/images/{Pn}_img0.png` 或其他合适的图片。

2. **论文关键图**：正文中至少引用 1-2 张论文原图（架构图/实验结果图等），让读者有直观感受。**注意：alt 必须为空字符串（`alt=""`），描述文字只放在 figcaption 中**，否则微信会同时渲染 alt 和 figcaption 导致出现两行描述：
```html
<figure style="margin: 20px 0; text-align: center;">
  <img src="{CDN_URL}" style="width: 100%; max-width: 640px; display: block; margin: 0 auto;" alt="">
  <figcaption style="font-size: 12px; color: #999; margin-top: 6px; line-height: 1.6;">图片说明（来源：原论文Figure N）</figcaption>
</figure>
```

3. **结尾格式**（严格遵守，与 P1 已发布文章一致）：
```html
<p>这是事实。</p>

<p style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #eee; font-size: 13px; color: #999;"><p style="margin-top: 16px; font-size: 13px; color: #666; word-break: break-all;">论文链接：<span style="color: #576b95;">{arxiv_url}</span></p>

kk的大模型论文学习笔记 · 第{N}篇 · {论文名}</p>
```

**禁止出现以下格式（AI痕迹太重）：**
- ❌ `<blockquote>` 一句话总结
- ❌ 📚 🔗 等 emoji 前缀
- ❌ "对入门者的启示" 等套路化小节
- ❌ 编号式要点总结（1. xxx 2. xxx 3. xxx）

4. **推送封面（thumb_image）**：JSON 中必须有 thumb_image 字段，指向 `wechat/covers/{Pn}_cover.png`（带标题文字的渐变 900x383 PNG）。

### Step 2: 生成封面图

封面图（卡片缩略图 + 文首封面）：900x383 带标题文字的渐变 PNG。

**使用 `generate_covers.py` 自动生成：**
```bash
cd ~/hermes-data/llm-paper-plan/wechat
python3 generate_covers.py articles/P6_ScalingLaws.json articles/P7_Chinchilla.json ...
```

脚本功能：
1. 从文章 JSON 读取 paper_id 和 title
2. 根据 COLOR_THEMES 选择配色（深色背景 + accent 色）
3. 生成带标题文字、accent 装饰线、论文英文名副标题的封面
4. 同时输出到两个目录：
   - `wechat/covers/{Pn}_cover.png` -- 推文卡片封面（thumb_image）
   - `wechat/images/covers/{Pn}_cover.png` -- 文章内部文首图（header）
5. 自动更新文章 JSON 的 `thumb_image` 字段指向 `wechat/covers/`

**新增论文时：** 在 `generate_covers.py` 的 `COLOR_THEMES` 和 `PAPER_NUMBERS` 字典中添加对应条目。

颜色方案：
- P1: 深蓝 accent蓝, P2: 紫色, P3: 绿色, P4: 橙色, P5: 红色
- P6: 天蓝, P7: 金黄, P8: 青色, P9: 紫罗兰, P10: 粉色
- P11: 深红, P12: 青绿, P13: 琥珀
- 阶段总结: 紫罗兰(S1), 天蓝(S2)

### Step 3: 处理文首封面图和正文图片

**文首封面图（Header Image）：**
1. 用 `generate_covers.py` 生成带标题文字的渐变封面（与 P1-P5 风格一致）
2. 封面文件保存在 `wechat/images/covers/{Pn}_cover.png`
3. 上传到微信：调用 upload_content_image() API (media/uploadimg 端点)
4. 拿到微信 CDN URL
5. 替换文章 HTML 中的第一个 `<img src="...">`（即文首图）

**注意：文首封面图 ≠ 推文卡片封面。** 文首封面是文章内部第一张图（渐变+文字），推文卡片封面是 `wechat/covers/` 下的 thumb_image。两者视觉相同但用途不同。

**正文中的论文关键图片：**
1. **优先提取嵌入位图**：用 `doc.extract_image(xref)` 从 PDF 提取原始高清图片
   - 检查图片大小 >= 10KB（过滤掉装饰性小图标）
   - 部分论文（P9, P10）有高质量嵌入图，直接用
2. **矢量图 fallback**：对于全矢量绘制的图（P6, P7, P8），用 PyMuPDF 渲染
   - 精准裁剪：基于 caption 坐标定位图表区域，不截多余内容
   - zoom=3 保证清晰度
3. 上传到微信拿到 CDN URL
4. 在正文中替换占位符

**论文链接**：所有单篇论文文章结尾必须包含 arXiv 链接（阶段总结除外）。

### Step 3.5: LaTeX 公式渲染（公式多的文章必做）

论文文章中涉及数学公式时，**不能**用纯文本平铺（如 `r(x,y) = β · log(π(y|x))`）。应使用 LaTeX 语法书写，由 `formula_render.py` 自动渲染为 SVG 公式图。

**公式书写规范：**

1. **块级公式**（独占一行，居中显示）：用 `<p>$$ ... $$</p>` 包裹
   ```html
   <p>$$r(x,y) = \beta \cdot \log\frac{\pi(y|x)}{\pi_{\text{ref}}(y|x)} + \beta \cdot \log Z(x)$$</p>
   ```
   渲染后自动替换整个 `<p>` 标签为居中的公式 SVG 图。

2. **行内公式**（文字中穿插）：用 `$ ... $` 包裹
   ```html
   <p>其中 $\beta$ 控制 KL 惩罚的强度，$\sigma$ 是 sigmoid 函数。</p>
   ```

3. **公式前后必须有引导语**：公式不是凭空出现的，前面至少有一句 "写成数学形式就是：" 或 "这个优化问题的最优解可以写成：" 之类的引导。

**LaTeX 速查表（论文高频符号）：**
> 完整速查表见 `references/formula-cheatsheet.md`，含对齐领域高频公式模板（DPO loss、Bradley-Terry、隐式奖励等）。

| 纯文本写法 | LaTeX 写法 | 渲染效果 |
|-----------|-----------|---------|
| π_θ(y\|x) | `\pi_\theta(y\|x)` | π_θ(y|x) |
| π_ref | `\pi_{\text{ref}}` | π_ref |
| σ(x) | `\sigma(x)` | σ(x) |
| log(a/b) | `\log\frac{a}{b}` | log(a/b) 分数形式 |
| exp(x) | `\exp(x)` | exp(x) |
| x → ∞ | `x \to \infty` | x → ∞ |
| ∝ | `\propto` | ∝ |
| E[...] | `\mathbb{E}[...]` | E[...] 期望符号 |
| β · x | `\beta \cdot x` | β·x |
| L_DPO | `L_{\text{DPO}}` | L_DPO |

**公式书写常见陷阱：**

1. **`>` 在公式中必须避免破坏 HTML**：`P(A > B)` 中的 `>` 会提前关闭 `<img>` 标签的 `alt` 属性，导致后面内容泄露为裸文本。`formula_render.py` 的 `latex_escape_html()` 会自动转义 `>` → `&gt;`、`<` → `&lt;`。

2. **下标命名一致性**：公式中的变量要在上下文中有对应。如 `y_w` = winner（好的回答）、`y_l` = loser（差的回答），在公式后面的文字中要解释清楚。如果不解释，读者不知道 `w` 和 `l` 是什么意思。

3. **块级公式前后不留裸文字**：`<p>最优策略 $$formula$$</p>` 会导致 `最优策略` 残留在公式图上方。应写为 `<p>最优策略可以写成：</p><p>$$formula$$</p>`，让前导文字自成一个段落。

4. **不要有重复 $$ 标记**：清理旧公式图片时，如果残留了 img 标签，重新运行 `formula_render.py` 会产生双重图片。清理时确保 `display:block` 的公式 img 全部移除。

5. **正文中的数学变量必须用行内公式渲染**：如 `y_w`、`y_l`、`π_θ`、`π_ref`、`log π(y|x)` 等带有下标的变量不能裸写在正文中。应全部用 `$...$` 包裹（如 `$y_w$`、`$\pi_\theta$`），让它们与块级公式中的变量格式统一。正文字段的表达式也应行内渲染，如 `$\log\pi_\theta(y_w|x) - \log\pi_\theta(y_l|x)$`。

6. **公式变量首次出现必须解释**：每个数学符号在首次出现时，紧跟在公式后面或前面用自然语言解释其含义。例如：
   - `$y_w$` = winner（人类偏好的回答），`$y_l$` = loser（被淘汰的回答）
   - `$\pi_\theta$` = 当前正在训练的 policy 模型，`$\pi_{\text{ref}}$` = 冻结的参考模型（锚点）
   - `$\beta$` = 控制 KL 惩罚强度的超参数
   
   原则：读者不能看到一个符号后要去猜它的意思。公式前后的文字就是符号的「类型声明」。

7. **变量命名全文一致性**：同一个概念在整个文章中必须用同一个变量名。例如正文说「当前模型」但公式用 $\pi_\theta$，必须在首次出现时明确建立映射：「当前模型（记作 $\pi_\theta$）」。之后所有引用保持一致——不要在正文中时而说「当前模型」时而说「$\pi_\theta$」，选一个主称呼并贯穿全文。

**关于公式渲染方式（重要）：**

微信文章不支持 MathJax/KaTeX 等 LaTeX 渲染引擎，也不接受外部域名图片。因此公式必须以**图片形式**嵌入，且图片必须上传到微信 CDN（mmbiz.qpic.cn）。

图片清晰度由 CodeCogs 的 `\dpi` 参数控制。**微信忽略 `<img>` 的 `height`/`max-width` CSS，图片始终按像素原大小显示，因此不能靠 CSS 缩放**。

当前使用 `\dpi{150}`（自然尺寸）。150 DPI 下：
- 行内公式如 `y_w` 约 16px 高，接近正文 14px，视觉上融为一体
- 块级公式约 25-45px 高，宽度自然适配

不要用 `\dpi{300}`——像素翻倍后图片 2x 大，微信无法 CSS 缩小。

**渲染命令：**

```bash
cd ~/hermes-data/llm-paper-plan/wechat

# 预览（不修改文件）
python3 formula_render.py --dry-run articles/P13_DPO.json

# 正式渲染
python3 formula_render.py articles/P13_DPO.json
```

工具位置：`wechat/formula_render.py`，渲染后端为 CodeCogs SVG API（免费，无需 API key）。

**注意：** 
- 微信文章只接受 `mmbiz.qpic.cn` 域名的图片，外部 URL（包括 CodeCogs 直链）会被吞掉。
  因此 `formula_render.py` 的完整流程是：CodeCogs 渲染 PNG → 下载本地 → 上传微信 CDN → 用 CDN URL 替换。
- 公式渲染后文章 HTML 中的公式会变为 `<img>` 标签，体积会增大（每个公式图约 10-30KB），但不影响微信显示。

### Step 4: 审稿（LLM 对比论文原文）【发布前必做】

审稿脚本：`wechat/review_article.py`

**审稿流程：**
1. 下载论文 PDF（缓存到 `/tmp/P{n}_paper.pdf`）
2. 用 PyMuPDF 提取正文（到 References 止，上限 15000 字）
3. 调用 LLM 对比论文原文 vs 文章纯文本
4. 输出分级审查报告 → `wechat/reviews/{P{n}}_review.json`

**审什么（5 类问题）：**
| 严重度 | 类型 | 示例 |
|--------|------|------|
| error | 明确事实错误 | 数字错误、方法描述错误、因果颠倒 |
| warning | 可能误导 | 过度简化、百分比与原文不一致 |
| suggestion | 可改进 | 比喻不够精准、省略了有价值的细节 |

**不审什么（允许的）：**
- 通俗比喻和口语化解释
- 省略次要细节
- 个人观点（只要不与原文矛盾）

**命令：**
```bash
cd ~/hermes-data/llm-paper-plan/wechat

# 单篇审稿
python3 review_article.py articles/P11_InstructGPT.json

# 审稿所有
python3 review_article.py --all

# 审稿 + 自动修正 error 级别问题
python3 review_article.py --fix articles/P1_xxx.json
```

**新增论文时必做：** 在 `review_article.py` 的 `PDF_SOURCES` 和 `ARTICLE_FILES` 字典中添加新论文的 PDF URL 和 JSON 文件名映射。

**审稿结果处理：**
- `good`：可以发布
- `acceptable`：修正 warning 后可发布
- `poor`：必须修正 error 后重新审稿

**前置条件：** 审稿调用 LLM API。密钥查找优先级：
1. `DEEPSEEK_API_KEY` 环境变量（Hermes gateway 同一来源）
2. `~/.zshrc` 中的 `DEEPSEEK_API_KEY`（自动 source 读取）
3. `~/.hermes/config.yaml` 中的 `api_key`（fallback）

如果 API 认证失败（401），检查密钥是否过期。`DEEPSEEK_API_KEY` 在 `~/.zshrc` 中定义，shell 不自动加载 profile 时需要手动 source 或依赖脚本自动读取。

### Step 4.5: Codex 第三方审稿（可选，推荐）

LLM 审稿受限于单一模型的判断能力。发布前建议用 OpenAI Codex CLI 做一次**独立第三方审稿**——不同模型、不同 prompt、不同的视角，能发现 LLM 审稿遗漏的问题。

**前置条件：** Codex CLI 已安装并通过 `codex login --device-auth` 认证。Codex 用 GPT-5.5 模型 + 联网搜索，能直接拉取 arXiv PDF 逐句核对。

**命令：**
```bash
cd ~/hermes-data/llm-paper-plan/wechat
codex exec --skip-git-repo-check "Read articles/P11_xxx.json, ... Fact-check each against original papers. Output in Chinese."
```

**Codex vs LLM 审稿对比：**
- 不同模型独立判断，不受 Hermes 自身 prompt 影响
- 能直接读 JSON 文件、联网搜索 arXiv PDF 原文
- 案例：P12 的宪法来源描述和 PM/feedback model 混淆，就是 Codex 发现而 LLM 审稿漏掉的

**4a. 论文链接验证（发布前必做）**

文章结尾的论文链接必须验证指向正确论文。特别是 P3(GPT-1) 和 P4(GPT-2) 不在 arXiv 上，不能靠 arXiv ID 猜测链接。

验证方法：
```bash
cd ~/hermes-data/llm-paper-plan/wechat
python3 << 'EOF'
import json, re, subprocess

LINKS = {
    "P1": "https://arxiv.org/abs/1706.03762",
    "P2": "https://arxiv.org/abs/1810.04805",
    "P3": "https://cdn.openai.com/research-covers/language-unsupervised/language_understanding_paper.pdf",
    "P4": "https://cdn.openai.com/better-language-models/language_models_are_unsupervised_multitask_learners.pdf",
    "P5": "https://arxiv.org/abs/2005.14165",
    "P6": "https://arxiv.org/abs/2001.08361",
    "P7": "https://arxiv.org/abs/2203.15556",
    "P8": "https://arxiv.org/abs/2205.14135",
    "P9": "https://arxiv.org/abs/2307.08691",
    "P10": "https://arxiv.org/abs/1910.02054",
    "P11": "https://arxiv.org/abs/2203.02155",
    "P12": "https://arxiv.org/abs/2212.08073",
    "P13": "https://arxiv.org/abs/2305.18290",
}

# 检查文章中的链接
for pid, fname in [("P3","P3_GPT1.json")]:  # 按需修改
    data = json.load(open(f"articles/{fname}"))
    content = data["content"]
    link_m = re.search(r'论文链接[：:]\s*<span[^>]*>([^<]+)</span>', content)
    actual = link_m.group(1) if link_m else "NOT FOUND"
    expected = LINKS.get(pid, "UNKNOWN")
    match = "OK" if actual == expected else "MISMATCH"
    print(f"{pid}: {match}")
    if match == "MISMATCH":
        print(f"  Expected: {expected}")
        print(f"  Actual:   {actual}")
EOF
```

对于 arXiv 链接，还应验证标题是否匹配：
```bash
curl -sL https://arxiv.org/abs/XXXX.XXXXX | grep -o 'citation_title" content="[^"]*"'
```

各论文正确链接（已验证）：
- P1: https://arxiv.org/abs/1706.03762 (Attention Is All You Need)
- P2: https://arxiv.org/abs/1810.04805 (BERT)
- P3: https://cdn.openai.com/research-covers/language-unsupervised/language_understanding_paper.pdf (GPT-1，不在arXiv)
- P4: https://cdn.openai.com/better-language-models/language_models_are_unsupervised_multitask_learners.pdf (GPT-2，不在arXiv)
- P5: https://arxiv.org/abs/2005.14165 (GPT-3)
- P6: https://arxiv.org/abs/2001.08361 (Scaling Laws)
- P7: https://arxiv.org/abs/2203.15556 (Chinchilla)
- P8: https://arxiv.org/abs/2205.14135 (FlashAttention)
- P9: https://arxiv.org/abs/2307.08691 (FlashAttention-2)
- P10: https://arxiv.org/abs/1910.02054 (ZeRO)
- P11: https://arxiv.org/abs/2203.02155 (InstructGPT)
- P12: https://arxiv.org/abs/2212.08073 (Constitutional AI)
- P13: https://arxiv.org/abs/2305.18290 (DPO)

**4b. LLM 审稿**

审稿脚本: `wechat/review_article.py`
- 从 PDF 提取论文原文（用 PyMuPDF）
- 调用 LLM 对比论文原文和文章内容
- 检查事实准确性：数字、方法描述、因果逻辑
- 输出分级报告：ERROR / WARNING / INFO
- overall_quality: excellent / good / acceptable / poor / dangerous

命令：
```bash
cd ~/hermes-data/llm-paper-plan/wechat
python3 review_article.py articles/P1_attention_is_all_you_need.json
```

审稿结果处理：
- excellent/good: 可以发布
- acceptable: 修正 WARNING 后可发布
- poor/dangerous: 必须修正 ERROR 后重新审稿

手动修正后用 publish! 跳过二次审稿直接发布。

### Step 5: 发布到公众号草稿箱

发布脚本: `wechat/wechat_publish.py`

```bash
# 先测试连通性
python3 wechat_publish.py test

# 查看当前出口IP（IP白名单问题排查）
python3 wechat_publish.py ip

# 单篇发布（跳过审稿，已审过）
python3 wechat_publish.py publish! articles/P1_attention_is_all_you_need.json

# 批量发布所有
python3 wechat_publish.py publish_all

# 查看发布状态
python3 wechat_publish.py status
```

发布日志: `wechat/published_log.json`，记录每篇的 media_id 和时间。重发需清空此文件。

重要提醒：
- 订阅号只能创建草稿，kk 需到公众号后台草稿箱手动发布
- 出口 IP 会频繁变化，导致 40164 白名单错误，发布前先 test 确认
- 旧版草稿无法通过 API 删除，需手动在后台清理

## 文件结构

```
wechat/
  config.json              # 微信 AppID/Secret
  wechat_publish.py        # 发布工具 v3 (含审稿)
  review_article.py        # LLM审稿模块
  generate_covers.py       # 封面生成工具（同时输出到 covers/ 和 images/covers/）
  formula_render.py        # LaTeX 公式渲染工具（CodeCogs SVG）
  upload_image.py          # 图片上传工具
  token_cache.json         # Token 缓存
  published_log.json       # 发布记录
  articles/                # 文章 JSON
    P1_attention_is_all_you_need.json
    P2_BERT.json
    P3_GPT1.json
    P4_GPT2.json
    P5_GPT3.json
    stage1_summary.json
  covers/                  # 推文卡片封面图（thumb_image 引用此目录）
    P1_cover.png           # 900x383 带标题文字渐变PNG
    ...
  images/
    covers/                # 文章内部文首第一张图（header image 引用此目录）
      P1_cover.png         # 与 covers/ 同款，供文首展示
      ...
    extracted/             # 从PDF提取的论文原图
    P1_figure.png          # 论文关键图（旧方式，已弃用）
    ...
  reviews/                 # 审稿报告
```

## Cron 自动发布流程（已停用）

**重要：cron 自动发布已暂停（job_id: 2995cf3322eb）。** 之前每天 21:00 自动检测并发布，导致 kk 不知情的情况下发布了 P8/P9 草稿。现在改为**仅 kk 主动要求时才发布**。

如需恢复自动发布，取消暂停该 cron job 即可。

## 公众号运营策略

### 当前状态

- 内容类型：大模型论文学习笔记（P1-P13 已发布，P14+ 待学习后撰写）
- 菜单栏入口：(1) AI 教育机构学习资料链接 (2) 朋友的 AI newsletter 产品
- 发布节奏：论文学完一篇发一篇，无固定周期

### 内容矩阵（不只是论文笔记）

论文笔记是主线，但不应是全部。建议扩展为三类内容：

1. **论文解读（主线，已有）**：每篇论文一篇深度文章，按学习计划推进
2. **热点快评（增量）**：重大 AI 新闻/发布时，用论文积累的知识快速给判断。比如"GPT-4o 发布——从 FlashAttention 的角度看，实时对话的技术难点在哪"。这类文章短（800-1500字），但观点要快、要准
3. **月度回顾（增量）**：每月一篇"这个月 AI 领域发生了什么"，用 before/after 框架梳理，展示技术敏锐度。读者需要的不是新闻汇总（有 AI newsletter 了），而是"kk 怎么看"

### 互动与增长

- **评论区运营**：每篇文章结尾抛一个开放式问题，鼓励读者讨论。比如"你觉得 BERT 和 GPT 两条路线，最终会融合还是会分道扬镳？"
- **菜单栏优化**：当前 2 个入口偏资源导流。建议增加"关于我"入口（个人介绍 + 公众号定位），以及"论文目录"入口（已发布的论文索引，方便新读者追）
- **朋友圈/社群分发**：文章发布后 kk 朋友圈转发，配一句有观点的导语（不是标题）
- **跨号合作**：朋友的 AI newsletter 可以互相推荐，形成互补（他推资讯，kk 推深度解读）

### 发布节奏建议

- 论文文章：学完就发，不囤稿
- 热点快评：事件后 24 小时内发，超过就跳过
- 月度回顾：每月最后一天或第一天
- 每周至少 1 篇内容保持存在感，哪怕是一段短评

## 图片处理流水线（关键！）

文章生成时图片 src 用占位符（`HEADER_IMAGE_PLACEHOLDER`、`FIGURE_1_PLACEHOLDER` 等），发布前必须替换成微信 CDN URL。

### 论文原图提取工具：extract_figures.py（核心工具）

`wechat/extract_figures.py` 是论文图片提取的一体化工具。功能：
1. 从论文 PDF 中根据 Figure caption 坐标精准裁剪图表区域
2. 用 PyMuPDF 渲染为高清 PNG（zoom=3）
3. 自动上传到微信 CDN
4. 替换文章 JSON 中的图片 URL

**新增论文时，分两步：**

**第一步：扫描 Figure 位置**（也可运行独立脚本 `scripts/scan_figure_positions.py <pdf_path>`）

```bash
cd ~/hermes-data/llm-paper-plan/wechat
python3 << 'PYEOF'
import fitz, re

pdf_path = "/tmp/P{N}_paper.pdf"  # 先下载 PDF
doc = fitz.open(pdf_path)
for pn in range(len(doc)):
    page = doc[pn]
    blocks = page.get_text("dict")["blocks"]
    for i, b in enumerate(blocks):
        if b["type"] == 0:
            text = " ".join(span["text"] for line in b["lines"] for span in line["spans"]).strip()
            m = re.match(r"Figure\s+(\d+)", text, re.IGNORECASE)
            if m and len(text) > 8:
                rect = fitz.Rect(b["bbox"])
                print(f"  Page {pn+1}: Figure {m.group(1)} at y={rect.y0:.0f}-{rect.y1:.0f}")
                print(f"    Caption: {text[:90]}")
PYEOF
```

**第二步：添加到 FIGURE_DEFS**

在 `extract_figures.py` 的 `FIGURE_DEFS` 字典中添加新论文条目：

```python
"P{N}": {
    "pdf": "/tmp/P{N}_paper.pdf",
    "page_width": 612,          # PDF 页面宽度
    "page_height": 792,         # PDF 页面高度
    "figures": [
        {
            "name": "fig1",
            "page": 1,          # 0-indexed 页码
            "caption_y_start": 250,  # Figure caption 顶部 Y 坐标
            "caption_y_end": 315,    # Figure caption 底部 Y 坐标
            "description": "论文图描述 (Figure 1)",
        },
        # ... 更多图 ...
    ]
},
```

**选择哪些图：** 优先选方法/架构示意图（Figure 1 或 Figure 2 通常是论文的核心方法图），其次是关键实验结果图。每篇文章 1-2 张图即可。

**提取 + 上传 + 替换：**

```bash
python3 extract_figures.py P11   # 处理单篇论文
```

提取完成后，图片保存在 `wechat/images/{paper_id}/`，已自动上传 CDN。然后需要手动将 figure HTML 嵌入文章 JSON 的适当位置：

```python
fig_html = """<figure style="margin: 20px 0; text-align: center;">
  <img src="{CDN_URL}" style="width: 100%; max-width: 640px; display: block; margin: 0 auto;" alt="">
  <figcaption style="font-size: 12px; color: #999; margin-top: 6px; line-height: 1.6;">描述（来源：原论文 Figure N）</figcaption>
</figure>"""
```

嵌入位置原则：图前必须有引导句（如"下面这张图展示了..."），图紧跟在相关技术描述之后。

**当前 FIGURE_DEFS 覆盖范围：** P6-P13（P1-P5 无配置，需要时手动添加）。

**常见问题与修复：**

1. **图片被截断（只提取到图的一小条）**：当论文图是流程图（包含大量文字标签，如 P12 CAI 的 Figure 1）时，PyMuPDF 会把图内的文字标签识别为独立文本块。旧版 `find_figure_bounds` 在 caption 上方找到最近的文本块就停，导致只截到图的底部。修复方案：增加聚合判断——如果 caption 上方所有文本块都较短（<80字符）且短文本块 ≥3 个，判定为「全图内标签」，使用页面顶部作为裁剪起点。

2. **提取后图片 <5KB**：脚本的 WARNING 回退机制会自动扩大裁剪区域重试。如果触发 WARNING，说明 `find_figure_bounds` 的启发式对此页面失效，需要检查该页面的文本块布局调整算法。

3. **PDF 缓存丢失**：`/tmp/P{n}_paper.pdf` 可能被系统清理。重新下载即可：
   ```bash
   curl -sL --proxy http://127.0.0.1:7897 -k -o /tmp/P{N}_paper.pdf https://arxiv.org/pdf/{arxiv_id}.pdf
   ```

### 正文图片：优先提取嵌入位图，矢量图用渲染 fallback

论文 PDF 中的图片有两种形式：
1. **嵌入位图**（JPEG/PNG）：可直接用 `doc.extract_image(xref)` 提取原始高清图片
2. **矢量绘图**（PGF/TikZ 等）：extract_image 返回空或极小图片，需用 PyMuPDF 渲染页面区域

**推荐策略：先 extract_image，失败再用渲染**

```python
def get_paper_figure(pdf_path, page_num, figure_index=0, render_region=None):
    """提取论文原图。优先用 extract_image，fallback 到页面渲染。"""
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    
    # Step 1: 尝试提取嵌入位图
    images = page.get_images(full=True)
    if figure_index < len(images):
        xref = images[figure_index][0]
        base_image = doc.extract_image(xref)
        if base_image and base_image["image"]:
            size_kb = len(base_image["image"]) // 1024
            if size_kb >= 10:  # 有意义的图片（非图标/装饰）
                img_data = base_image["image"]
                ext = base_image["ext"]
                # 保存并上传
                out_path = f"/tmp/{paper_id}_fig{figure_index}.{ext}"
                with open(out_path, "wb") as f:
                    f.write(img_data)
                doc.close()
                return out_path
    
    # Step 2: Fallback - 渲染 PDF 页面区域
    if render_region:
        mat = fitz.Matrix(8, 8)  # 8x zoom for vector-quality
        pix = page.get_pixmap(matrix=mat, clip=fitz.Rect(render_region))
        out_path = f"/tmp/{paper_id}_fig{figure_index}_rendered.png"
        pix.save(out_path)
        doc.close()
        return out_path
    
    doc.close()
    return None
```

**各论文情况参考：**
- P1-P5: 矢量为主，需渲染
- P6, P7: 全矢量（P6只有10x210px装饰条，P7只有875x216px logo），extract_image 无可用图，必须渲染
- P8: 正文 Figure 是矢量，附录有嵌入图（page 28-30，114-125KB），正文图需渲染
- P9: 有高质量嵌入图（page 4: 5844x3018, page 8: 2298x1268, page 9: 3710x2194）
- P10: 有嵌入图（page 3: 2902x1345, page 4: 2223x897, page 5: 2343x1078）

**渲染质量：** 矢量图渲染用 8x zoom（输出约 4400px 宽），在微信 900px 显示宽度下视觉等价矢量图。微信不支持 SVG 内嵌，必须转 PNG。

### 矢量图渲染方法（精准裁剪）

不要截取整个 PDF 页面（会包含标题、页码等多余内容），而是精准裁剪图表区域：

**Step 1: 扫描 PDF 找 Figure caption 坐标**
```python
import fitz
doc = fitz.open(pdf_path)
for pn in range(len(doc)):
    page = doc[pn]
    blocks = page.get_text("dict")["blocks"]
    for i, b in enumerate(blocks):
        if b["type"] == 0:
            text = " ".join(span["text"] for line in b["lines"] for span in line["spans"]).strip()
            if text.lower().startswith("figure") and len(text) > 8:
                rect = fitz.Rect(b["bbox"])
                print(f"  Page {pn+1}, Block {i}, y={rect.y0:.0f}-{rect.y1:.0f}: {text[:80]}")
                # Show block above (actual figure content)
                if i > 0 and blocks[i-1]["type"] == 0:
                    prev = fitz.Rect(blocks[i-1]["bbox"])
                    print(f"    Prev block y={prev.y0:.0f}-{prev.y1:.0f}")
```

**Step 2: 确定裁剪区域并渲染（必须包含 Figure caption）**

渲染区域应包含完整的 Figure 内容和其 caption 说明文字，让读者看到和论文原文一样的完整图表。**不要硬编码坐标**，使用自动检测：

```python
import re

def find_figure_region(page, figure_num, padding=20):
    """自动检测 Figure 区域，包含完整图表+caption"""
    blocks = page.get_text("dict")["blocks"]
    pw = page.rect.width
    
    # 1. 找 caption 文字块 ("Figure N:")
    caption_rect = None
    caption_idx = None
    for i, b in enumerate(blocks):
        if b["type"] == 0:
            text = " ".join(span["text"] for line in b["lines"] for span in line["spans"]).strip()
            if re.match(rf"Figure\s+{figure_num}[\s:.|]", text, re.IGNORECASE):
                caption_rect = fitz.Rect(b["bbox"])
                caption_idx = i
                break
    
    if not caption_rect:
        return None
    
    # 2. 找顶部边界：向上搜索上一个 section 标题或 Figure caption
    fig_top = 35  # 默认：页面顶部附近
    for j in range(caption_idx - 1, -1, -1):
        b = blocks[j]
        if b["type"] == 0:
            text = " ".join(span["text"] for line in b["lines"] for span in line["spans"]).strip()
            bbox = fitz.Rect(b["bbox"])
            is_prev_caption = re.match(r"Figure\s+\d", text, re.IGNORECASE)
            # 真正的章节标题：如 "1.2 Summary" 或 "3 Approach"，不是 "1.0B" 这类数字
            is_section = bool(re.match(r"^\d+\.\d+\s+[A-Z]", text)) or \
                         (re.match(r"^\d+\s+[A-Z]", text) and len(text) > 10 and not re.search(r"\d{3,}", text))
            if is_prev_caption or is_section:
                fig_top = bbox.y1 + 8
                break
    
    # 3. 底部 = caption 底部 + padding，左右 = 全页宽（小边距）
    return fitz.Rect(15, fig_top, pw - 15, caption_rect.y1 + padding)

# 渲染
region = find_figure_region(page, figure_num=1)
mat = fitz.Matrix(8, 8)  # 8x zoom for vector-quality output (~4400px wide)
pix = page.get_pixmap(matrix=mat, clip=region)
pix.save(output_path)
```

**关键点：**
- 左右边距只用 15px，确保捕获坐标轴标签
- 顶部自动向上搜索直到上一个 section 或 caption
- 底部 = caption 末尾 + 20px padding
- 不要用硬编码坐标，容易切掉内容

**Step 3: 上传到微信 CDN 并替换文章中的图片 URL**
```python
from wechat_publish import get_token, upload_content_image
cdn_url = upload_content_image(get_token(), output_path)
# 替换文章中的 body figure（跳过第一个 = header）
urls = re.findall(r'(http://mmbiz\.qpic\.cn/[^"]+)', content)
content = content.replace(urls[1], cdn_url, 1)  # 替换第1个body图
```

### 文首封面图（Header Image）-- 用 generate_covers.py 生成

每篇文章 HTML 开头需要文首封面图。**使用 `generate_covers.py` 生成带标题文字的渐变封面图**，风格与 P1-P5 保持一致。

封面特征：900x383，深色背景渐变 + 论文标题文字 + accent 色装饰线 + 论文英文名副标题。

```bash
cd ~/hermes-data/llm-paper-plan/wechat
# 生成单篇封面
python3 generate_covers.py articles/P6_ScalingLaws.json
# 批量生成
python3 generate_covers.py articles/P6_ScalingLaws.json articles/P7_Chinchilla.json ...
```

脚本会：
1. 从文章 JSON 读取 paper_id 和 title
2. 根据 COLOR_THEMES 选择配色
3. 生成带标题文字的渐变封面到 `images/covers/{paper_id}_cover.png`
4. 自动更新文章 JSON 的 `thumb_image` 字段

**新增论文时必须做的事：**
在 `generate_covers.py` 的 `COLOR_THEMES` 和 `PAPER_NUMBERS` 中添加对应条目。

封面图生成后需要：
1. 上传为文首封面：`upload_content_image()` -> CDN URL
2. 替换 HTML 中的 `HEADER_IMAGE_PLACEHOLDER`
3. 上传为 thumb（卡片缩略图）：`wechat_publish.py publish!` 会自动处理

### 文章结尾论文地址

所有单篇论文文章必须在结尾包含论文链接，格式：
```html
<p style="margin-top: 16px; font-size: 13px; color: #666; word-break: break-all;">论文链接：<span style="color: #576b95;">https://arxiv.org/abs/{paper_id}</span></p>

kk的大模型论文学习笔记 · 第{N}篇 · {论文名}</p>
```

阶段总结文章不需要论文链接，只用简单 footer。

### 完整图片处理流程

```bash
# 1. 确保 PDF 已缓存（审稿时自动下载到 /tmp/P{n}_paper.pdf）
# 2. 生成封面图（自动更新 thumb_image 字段）
python3 generate_covers.py articles/P11_xxx.json
# 3. 上传正文图片到 CDN 并替换占位符
python3 << 'EOF'
import fitz, re, json, sys
sys.path.insert(0, '.')
from wechat_publish import get_token, upload_content_image

# 方法1: 直接提取嵌入位图（适用于 P9, P10 等有嵌入图的论文）
doc = fitz.open("/tmp/P11_paper.pdf")
page = doc[page_num]
img_info = page.get_images(full=True)[0]
base_image = doc.extract_image(img_info[0])
with open("/tmp/P11_fig1.png", "wb") as f:
    f.write(base_image["image"])
cdn_url = upload_content_image(get_token(), "/tmp/P11_fig1.png")
# ... 替换文章中的占位符

# 方法2: 渲染矢量图（适用于 P6, P7, P8 等全矢量论文）
mat = fitz.Matrix(8, 8)  # 8x zoom, ~4400px wide
region = (x0, y0, x1, y1)  # 根据caption定位的精确区域
pix = page.get_pixmap(matrix=mat, clip=fitz.Rect(region))
pix.save("/tmp/P11_fig1.png")
cdn_url = upload_content_image(get_token(), "/tmp/P11_fig1.png")
EOF

# 4. 验证无残留占位符
python3 -c "
import json, re
data = json.load(open('articles/P11_xxx.json'))
placeholders = re.findall(r'HEADER_IMAGE_PLACEHOLDER|FIGURE[_A-Z0-9_]*PLACEHOLDER', data['content'])
print('Remaining:', placeholders if placeholders else 'NONE - OK')
"
```

### 重发前必须清 published_log

修正文章内容或图片后重发，必须先清除旧记录：
```bash
cd ~/hermes-data/llm-paper-plan/wechat
python3 -c "
import json
stage_ids = {'P6','P7','P8','P9','P10','stage2_summary'}  # 按需修改
log = json.load(open('published_log.json'))
log = [e for e in log if e['paper_id'] not in stage_ids]
json.dump(log, open('published_log.json','w'), ensure_ascii=False, indent=2)
"
```

## 论文图与上下文匹配度 Review（发布前必做）

文章中嵌入的论文图必须与周围文字描述一致。常见问题：alt/caption 与图内容不符、图内容与上下文不匹配、缺少 figcaption。

**Review 方法：**

1. 提取文章中所有 `<figure>` 块的 alt、figcaption、上下文文字
2. 从 PDF 提取所有 Figure caption（用 `page.get_text("dict")` 搜索 "Figure N"）
3. 从 PDF 的 Figure 区域提取文字内容（坐标轴标签、数据表格等），确认图实际内容
4. 逐个核对：
   - alt 文本是否准确描述图的**实际内容**（不是期望内容）
   - figcaption 是否存在且描述正确（含"来源：原论文 Figure N"）
   - 图内容是否与文章中嵌入位置的上下文描述一致
   - 如果不匹配：要么换一张更合适的图，要么调整上下文文字

**典型错误模式：**
- 论文 Figure 是复合图（如 P8 Fig1 = tiling图 + memory hierarchy + runtime），alt 只描述了其中一部分
- caption 写"显存对比"但图实际是 throughput/speedup 数据（P10 Fig2）
- alt 写"GPU Utilization"但图实际是算法流程图（P9 Fig1）
- 上下文讲 A vs B 对比，但嵌入的图是训练曲线而非 benchmark 对比（P7 Fig2）

## 审稿脚本维护

`review_article.py` 的 `PDF_SOURCES` 和 `ARTICLE_FILES` 字典需要手动维护，新增论文时必须添加：
- PDF_SOURCES: arxiv URL + 本地缓存路径
- ARTICLE_FILES: JSON 文件名（注意实际文件名，如 `P6_ScalingLaws.json` 不是 `P6_Scaling_Laws.json`）

阶段总结文章（stage2_summary）无法对比单篇 PDF，审稿脚本会跳过。

## 常见问题

1. IP 白名单 40164: 出口 IP 不稳定，发布前 python3 wechat_publish.py ip 查当前 IP，去 mp.weixin.qq.com 添加
2. 重发文章: 清空 published_log.json 中对应条目，重新发布
3. 图片上传: 文首封面和正文图片都通过 media/uploadimg 上传（返回 CDN URL），封面缩略图通过 material/add_material 上传（返回 media_id）
4. 审稿失败(PDF不可获取): 用 `publish!` 跳过审稿直接发布，cron 模式下不要让审稿阻断流程
5. 已发布判断: published_log.json 中存在对应 paper_id 的条目即视为已发布，publish 脚本的 `is_published()` 也是这个逻辑
6. find_figure_bounds 的 region 安全检查: 如果计算出的 figure_top >= caption_y_start，说明文字块排序有问题，必须回退到默认值（如 y=50），否则 `fitz.Rect(top > bottom)` 会报错
7. 矢量图 vs 位图: 先用 extract_image 尝试提取，返回空或 <10KB 再用渲染 fallback
8. 新增论文封面: 必须在 generate_covers.py 的 COLOR_THEMES 和 PAPER_NUMBERS 中添加条目
9. 两个 covers 目录: `wechat/covers/` 是推文卡片封面（thumb_image 引用），`wechat/images/covers/` 是文章内部文首图（header 引用），不要混淆
10. 渲染矢量图必须包含 Figure caption: 裁剪区域从图表内容顶部到 caption 底部，不要去掉 caption 说明文字
11. P6/P7/P8 无法用 extract_image 提取正文原图: 这些论文的 Figure 全部是矢量绘制（matplotlib/PGF），PDF 中没有对应位图。唯一方式是 PyMuPDF 渲染，8x zoom 输出 4400+px 宽，在微信 900px 显示下视觉等价矢量。微信不支持 SVG 内嵌（只接受 PNG/JPG/GIF），所以即使提取了 SVG 也必须转 PNG
12. 矢量图渲染 zoom 值: 用 8x zoom (fitz.Matrix(8,8))，输出约 4400px 宽，保证在微信文章中放大查看不失真
13. 裁剪精度: 不要硬编码坐标！用 find_figure_region() 自动检测 caption + 向上搜索 section 边界。硬编码坐标容易切掉坐标轴标签（如 "1T"、"100B" 等）或 caption 文字
15. 论文图 figure 标签中：alt 必须为空字符串（alt=""），figure 内部不能有 <p> 标签做图片描述（与 figcaption 同时渲染会出现两行）。描述只放 figcaption，格式：`<figcaption style="text-align:center;font-size:14px;color:#888;margin-top:8px;">描述（来源：原论文Figure N）</figcaption>`。发布前检查每个 figure 标签内部是否同时存在 <p> 和 <figcaption>，如有则删除 <p>
16. 图文匹配 Review: 发布前必须核对每个论文图的 alt、figcaption、实际内容、上下文描述四者一致。常见错误：复合图 alt 只描述一部分、caption 与图实际内容不符、上下文讲对比但图是训练曲线。如果图与上下文不匹配，优先换一张更贴切的论文原图
17. Figure 序号验证: figcaption 中标注的 "Figure N" 必须与论文原文一致。验证方法：(1) 用宽 regex 搜索论文 PDF 所有 Figure 编号（注意部分论文用 `Figure N |` 而非 `Figure N:` 作分隔符，regex 应覆盖 `Figure\\s+\\d+\\s*[|:.\\s]`）(2) 确认文章引用的 Figure 编号确实存在于论文中 (3) 确认嵌入的图片内容与标注的 Figure 编号对应（可通过图片尺寸对比验证：下载 CDN 图片获取尺寸，与论文 extract_image 提取的原图尺寸比较）。绝对不能靠猜测编号——必须从论文原文确认
18. 论文 PDF 来源: P3(GPT-1)和P4(GPT-2)不在arXiv上，直接用arXiv ID下载会得到错误论文。正确URL: P3=https://cdn.openai.com/research-covers/language-unsupervised/language_understanding_paper.pdf, P4=https://cdn.openai.com/better-language-models/language_models_are_unsupervised_multitask_learners.pdf。下载后务必检查首页标题确认是正确论文
19. 发布前系统化检查清单（用脚本一键扫描所有文章）: (1) 所有非封面figure的alt必须为空字符串 (2) figure内部不能有`<p>`标签（与figcaption冲突渲染两行）(3) figcaption不能有重复来源标注如"（来源：原论文Figure N）"出现两次 (4) figcaption中的Figure编号必须用宽regex从论文PDF验证存在 (5) 无blockquote/emoji等禁止格式。脚本模板见 `/tmp/check_p345.py` 的检查逻辑
20. 论文图的选择原则（面向工程侧读者，无深厚算法背景）:
    - **0号规则：嵌入的图必须和上下文描述匹配，且是论文核心图**: 在将图片嵌入文章前，必须验证：(a) 图片实际内容与 figcaption 中的 Figure 编号一致（不能 Figure 3 的图标成 Figure 2），(b) 图片内容与上下文文字描述匹配（如上下文讲"三步流程"就不能嵌评估柱状图），(c) 嵌入的图是论文核心方法/贡献相关的图（如方法架构图、核心流程图），而非辅助性评估图表。**发布前逐张核对图片尺寸、figcaption、上下文三者是否一致。P11 曾出现 Figure 1（1596x597评估柱状图）被误标为 Figure 2（1596x741三步流程图）的问题。**
    - **图为观点撑腰**: 选的图必须能直接支撑论文的核心观点/核心贡献，不要选消融实验、辅助分析等佐证性图表。每张图读者看完应该能得出"原来如此"的感觉
    - **直观易懂优先**: 优先选一眼能看懂的图（如趋势折线图、架构对比图、流程示意图），避免选满是公式的架构细节图、密集的数据表格
    - **看不懂就配文字**: 如果论文核心图确实有理解门槛（如多面板图、坐标轴含义不直观），必须在 figcaption 或图前后的正文中用大白话解释"看这张图要注意什么"。例如：P4的Figure 1有12张小图，figcaption 要告诉读者"横轴是模型参数量，纵轴是准确率，趋势向上"
    - **用工程类比降低理解成本**: figcaption 和引导文字用工程术语类比（如 GPT-1的任务转换 = "统一的API接口，不同业务只调整入参格式"；GPT-3的few-shot = "给新同事看几个示例就能照着做"）
    - **移动端可读性**: 微信文章主要在手机上阅读（900px宽），避免选细节太多、字太小的图。如果原图是多面板图，考虑裁剪到最核心的1-2个面板
    - **图前加引导句**: 在 `<figure>` 标签前加一句 `<p>` 引导读者看图，格式："下面这张图..."或"看这张图，注意..."，帮助读者建立预期再去看图
21. **编辑文章 JSON 的坑——不要用 patch 工具**: 文章 JSON 的内容字段里包含大量 HTML 转义字符（`\\"`、`\\n` 等），`patch` 工具的 `old_string` 匹配极容易因转义差异而失败（P12 曾因此修了两次才成功）。**修改文章内容时，一律用 `execute_code` 写 Python 脚本**：先 `json.load()` 读入，用 `str.replace()` 做替换，再 `json.dump()` 写回。这样完全绕开转义问题。
