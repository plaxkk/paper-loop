---
{
  "slug": "gpt-2",
  "title": "让任务以文本的形式出现",
  "englishTitle": "Language Models are Unsupervised Multitask Learners",
  "date": "2019-02-14",
  "year": 2019,
  "stage": 1,
  "topic": "预训练",
  "difficulty": "基础",
  "minutes": 9,
  "source": "https://cdn.openai.com/better-language-models/language_models_are_unsupervised_multitask_learners.pdf",
  "arxiv": null,
  "contribution": "探索更大规模语言模型在多种任务上的零样本迁移。",
  "problem": "为每个任务单独收集标注并微调，限制了通用性和迁移方式。",
  "status": "draft",
  "glossary": [
    {
      "term": "零样本",
      "definition": "推理时不提供该任务的示例，也不进行任务专用参数更新。"
    },
    {
      "term": "自回归",
      "definition": "依据已有序列预测后续词元。"
    }
  ]
}
---

## 先读结论

GPT-2 把多个任务看成同一个文本预测问题：任务说明、上下文和答案可以出现在一段序列中。它展示了零样本迁移的可能性，也保留了明显不足。

## 历史位置

沿 GPT-1 的自回归预训练路线扩展模型和训练数据，同时更集中地研究不进行任务专用微调的表现。

## 核心机制

训练目标仍是预测下一个词。网络、词元化和训练数据规模等因素共同变化。推理时通过上下文组织翻译、问答、摘要等任务，不为每个评测任务重新训练一套参数。

**工程类比：**任务协议逐渐从单独的 API 输出头，转向在文本上下文中描述输入和预期输出；这只是类比，模型并不会因此获得严格的接口契约。

## 实验依据

报告比较语言建模以及阅读理解、翻译、摘要等任务的迁移效果，并展示生成样本。语言模型损失下降和具体任务表现改善需要分别检查。

## 局限与误区

零样本结果在任务之间差别很大，不能等同于可靠地执行任意指令。数据覆盖、评测污染和生成真实性也需要谨慎对待。

## 继续阅读

先读 ZeRO 与 Scaling Laws 理解训练成本，再读 GPT-3 看少样本上下文学习。

## 原文与审校

[阅读论文原文](https://cdn.openai.com/better-language-models/language_models_are_unsupervised_multitask_learners.pdf)。以上为编辑初稿；正式发布前须按原文复核实验、版本、图表与历史表述。
