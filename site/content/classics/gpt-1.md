---
{
  "slug": "gpt-1",
  "title": "先学习语言，再适应任务",
  "englishTitle": "Improving Language Understanding by Generative Pre-Training",
  "date": "2018-06-11",
  "year": 2018,
  "stage": 1,
  "topic": "预训练",
  "difficulty": "基础",
  "minutes": 9,
  "source": "https://cdn.openai.com/research-covers/language-unsupervised/language_understanding_paper.pdf",
  "arxiv": null,
  "contribution": "把无监督语言建模与有监督任务微调连接起来。",
  "problem": "不同语言理解任务通常需要大量标注和专门设计的模型。",
  "status": "draft",
  "glossary": [
    {
      "term": "预训练",
      "definition": "先在较通用的数据上学习参数。"
    },
    {
      "term": "微调",
      "definition": "在具体任务数据上继续更新模型参数。"
    }
  ]
}
---

## 先读结论

GPT-1 的核心是训练流程：先通过预测后续词学习通用表示，再使用标注数据适应具体任务。架构和训练目标一起决定了它能看到什么信息。

## 历史位置

Transformer 提供了可并行训练的注意力架构。本文采用其解码器式结构，探索生成式预训练对自然语言理解任务的帮助。

## 核心机制

第一阶段使用语言模型目标，按此前的词预测下一个词；第二阶段调整输入格式并增加任务输出层，用监督目标更新模型。分类、文本蕴含和相似度等任务通过不同的输入拼接方式进入共享模型。

$$
\mathcal{L}_{LM}=\sum_t\log P(x_t\mid x_{<t})
$$

**工程类比：**共享的预训练模型类似一个已学到通用数据结构的基础组件；微调仍要改变参数，不能等同于只在提示中放几个例子。

## 实验依据

论文在分类、蕴含、问答和语义相似度等任务中评估，并通过移除预训练、调整层数等实验分析收益。阅读时应区分整体任务结果与消融实验各自回答的问题。

## 局限与误区

它仍依赖任务数据进行微调，任务输入也需要适配。自回归目标只能读取此前上下文；这与后面的 BERT 掩码语言建模不同。

## 继续阅读

接着读 BERT，比较双向上下文与自回归目标；再读 GPT-2，观察生成式路线的规模扩展。

## 原文与审校

[阅读论文原文](https://cdn.openai.com/research-covers/language-unsupervised/language_understanding_paper.pdf)。以上为编辑初稿；正式发布前须按原文复核实验、版本、图表与历史表述。
