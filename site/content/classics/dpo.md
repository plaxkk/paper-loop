---
{
  "slug": "dpo",
  "title": "偏好优化，可以直接一些",
  "englishTitle": "Direct Preference Optimization: Your Language Model is Secretly a Reward Model",
  "date": "2023-05-29",
  "year": 2023,
  "stage": 4,
  "topic": "对齐",
  "difficulty": "进阶",
  "minutes": 12,
  "source": "https://arxiv.org/abs/2305.18290",
  "arxiv": "2305.18290",
  "contribution": "将特定偏好优化问题重写为直接训练语言模型的目标。",
  "problem": "奖励模型与强化学习组合的训练流程较复杂，稳定性和工程实现都存在成本。",
  "status": "draft",
  "glossary": [
    {
      "term": "参考策略",
      "definition": "用来约束优化或构造概率比的基准模型。"
    },
    {
      "term": "偏好对",
      "definition": "同一提示下较受偏好与较不受偏好的两个回答。"
    }
  ]
}
---

## 先读结论

DPO 在特定推导条件下，把偏好学习写成可直接优化的分类式损失。它不需要在训练流程里显式拟合一个独立奖励模型，但仍依赖偏好数据。

## 历史位置

接在 RLHF 讨论后，重点看训练目标如何改变。偏好优化并不等于已经解决真实性、可靠性或所有对齐问题。

## 核心机制

给定同一提示下的偏好回答和非偏好回答，目标比较策略模型相对于参考模型的对数概率比。参考模型和温度式系数控制优化的尺度与约束。

$$
\mathcal{L}_{DPO}=-\mathbb{E}\left[\log\sigma\left(\beta\log\frac{\pi_\theta(y_w\mid x)}{\pi_{ref}(y_w\mid x)}-\beta\log\frac{\pi_\theta(y_l\mid x)}{\pi_{ref}(y_l\mid x)}\right)\right]
$$

公式中的比较是偏好回答相对非偏好回答，不是无条件提高所有训练样本的概率。

## 实验依据

原文在情感控制、摘要和对话等任务中比较偏好学习方法。比较结论需要保留数据、模型和评测设置，不能直接推导出任何场景 DPO 都优于 PPO。

## 局限与误区

偏好数据质量、参考策略和超参数仍然重要。离线偏好学习的数据覆盖与分布偏移会影响结果。

**回顾性判断：**到这里可以把架构、规模、效率和对齐四条线重新连接，但第一卷仍不是大模型全部发展的完整历史。

## 继续阅读

回看 InstructGPT 对照训练流程；回看 Scaling Laws，区分“预测得更好”和“回答更符合偏好”两个目标。

## 原文与审校

[阅读论文原文](https://arxiv.org/abs/2305.18290)。以上为编辑初稿；正式发布前须按原文复核实验、版本、图表与历史表述。
