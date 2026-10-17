import { pageMetadata } from '@/lib/seo';
import { classics } from '@/lib/classics';
import { Timeline } from '@/components/timeline';
import { Footer } from '@/components/footer';
export const metadata=pageMetadata("大模型经典论文学习路线：Transformer、GPT、BERT 到对齐","按首次公开时间浏览 2017—2023 年经典 AI 论文，理解架构、预训练、规模化、训练效率与对齐之间的联系，阅读 kk 已发表的中文解读。","/timeline");
export default function Page(){const papers=classics();return <><main id="main" className="shell page-main"><div className="page-heading"><div className="eyebrow">THE CLASSICS / VOL. 01</div><div className="heading-row"><h1>大模型的来路。</h1><span className="mono subtle">2017 — 2023 · {papers.length} PAPERS</span></div><p>把重要论文放回历史坐标，理解每一步为什么发生。<br/>从架构、预训练到规模化与对齐，沿着问题的变化往前读。</p></div><Timeline papers={papers}/></main><Footer/></>;}
