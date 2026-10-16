---
{
  "slug": "flashattention",
  "title": "注意力加速，关键在数据搬运",
  "englishTitle": "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness",
  "date": "2022-05-27",
  "year": 2022,
  "stage": 3,
  "topic": "训练效率",
  "difficulty": "进阶",
  "minutes": 11,
  "source": "https://arxiv.org/abs/2205.14135",
  "arxiv": "2205.14135",
  "contribution": "通过分块和重计算减少显存读写，精确计算标准注意力。",
  "problem": "注意力计算中的大型中间矩阵会造成显存容量和读写开销。",
  "status": "draft",
  "glossary": [
    {
      "term": "IO 感知",
      "definition": "把存储层级之间的数据读写作为算法成本考虑。"
    },
    {
      "term": "在线 softmax",
      "definition": "在分块处理中累积并正确归一化 softmax。"
    }
  ]
}
---

## 先读结论

FlashAttention 是面向硬件存储层级的注意力算法实现。它保留标准注意力的数学结果，不能简单称为稀疏近似。

## 历史位置

Transformer 提供注意力结构。长序列和更大规模训练让实际显存访问成为关键瓶颈，需要从 FLOPs 之外看成本。

## 核心机制

把 Q、K、V 分块，在更快的片上存储中计算；利用在线 softmax 合并分块结果，避免把完整注意力矩阵反复写入高带宽显存。反向传播采用重计算，在额外计算和访存之间取舍。

**工程类比：**把中间数据留在更靠近计算单元的地方，减少往返搬运。它改变执行计划，并不意味着把所有数学运算消掉。

## 实验依据

论文分析 IO 复杂度，并在不同序列长度、硬件和模型设置中比较速度与显存。实际收益要看输入形状与硬件，不能只用一个加速数字描述。

## 局限与误区

精确算法也存在浮点误差和实现条件。更低的 IO 开销不等于注意力理论计算复杂度消失，也不意味着任意硬件都能获得相同收益。

## 继续阅读

回到对齐路线阅读 Constitutional AI，理解效率与行为优化是不同维度。

## 原文与审校

[阅读论文原文](https://arxiv.org/abs/2205.14135)。以上为编辑初稿；正式发布前须按原文复核实验、版本、图表与历史表述。
