import { pageMetadata } from '@/lib/seo';
import { classics } from '@/lib/classics';
import { Timeline } from '@/components/timeline';
import { Footer } from '@/components/footer';
export const metadata=pageMetadata("大模型经典论文学习路线：Transformer、GPT、BERT 到对齐","按首次公开时间浏览 2017—2023 年经典 AI 论文，理解架构、预训练、规模化、训练效率与对齐之间的联系，阅读 kk 已发表的中文解读。","/timeline");
export default function Page(){const papers=classics();return <><main id="main" className="shell page-main"><div className="page-heading"><div className="eyebrow">THE CLASSICS / VOL. 01</div><div className="heading-row"><h1>大模型的来路。</h1><span className="mono subtle">2017 — 2023 · {papers.length} PAPERS</span></div><p>从 Transformer 读起，看看大模型是怎么一步步发展起来的。<br/>每篇讲清楚：当时卡在哪儿，这篇论文解决了什么问题。</p></div><Timeline papers={papers}/></main><Footer/></>;}
