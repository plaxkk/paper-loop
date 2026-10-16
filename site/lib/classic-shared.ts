// Browser-safe exports; filesystem access stays in classics.ts.
export type { Classic } from './classics';
export const stages = [
 {title:'架构的转折',years:'2017',description:'先改变计算的方式，再重新思考语言建模。Transformer 是这段路线的起点。'},
 {title:'预训练成为共同语言',years:'2018—2019',description:'从任务专用模型走向通用预训练。GPT 与 BERT 在生成和理解两个方向探索，路线并不相同。'},
 {title:'规模带来的新问题',years:'2019—2020',description:'参数、数据与计算一起增长。能力的扩展和训练系统的限制，需要同时理解。'},
 {title:'把能力变成可用的模型',years:'2022',description:'算力如何分配、训练如何加速、模型如何理解人的意图，是并行发展的几条线。'},
 {title:'对齐与效率继续演进',years:'2023',description:'偏好优化和训练内核，分别沿着训练目标与硬件利用率继续改进。'},
];
