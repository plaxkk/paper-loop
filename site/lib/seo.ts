import type { Metadata } from 'next';
import type { Classic } from './classics';
export const SITE_URL = 'https://paper-loop.kkplayit.online';
export const SITE_NAME = 'Paper Loop';
export const absoluteUrl = (path: string) => path === '/' ? SITE_URL : new URL(path, SITE_URL).href;
export function pageMetadata(title: string, description: string, path: string): Metadata {
  return { title, description, alternates: { canonical: absoluteUrl(path) },
    openGraph: { type: 'website', siteName: SITE_NAME, locale: 'zh_CN', url: absoluteUrl(path), title, description,
      images: [{ url: absoluteUrl('/opengraph-image'), width: 1200, height: 630, alt: 'Paper Loop — AI classic paper reading notes' }] },
    twitter: { card: 'summary_large_image', title, description, images: [absoluteUrl('/opengraph-image')] } };
}
export function articleMetadata(paper: Classic): Metadata {
  const titles: Record<string,string> = {
    'transformer':'Transformer 论文解读：自注意力与多头注意力',
    'gpt-1':'GPT-1 论文解读：生成式预训练与微调',
    'bert':'BERT 论文解读：双向预训练与掩码语言模型',
    'gpt-2':'GPT-2 论文解读：语言模型与零样本学习',
    'zero':'ZeRO 论文解读：优化器状态分片与大模型训练',
    'scaling-laws':'Scaling Laws 论文解读：参数、数据与计算的规模法则',
    'gpt-3':'GPT-3 论文解读：少样本学习与上下文学习',
    'chinchilla':'Chinchilla 论文解读：计算最优的模型与数据规模',
    'flashattention':'FlashAttention 论文解读：IO 感知的精确注意力',
    'instructgpt':'InstructGPT 论文解读：人类反馈与 RLHF 对齐',
    'constitutional-ai':'Constitutional AI 论文解读：宪法式 AI 与模型对齐',
    'flashattention-2':'FlashAttention-2 论文解读：注意力计算的并行优化',
    'dpo':'DPO 论文解读：直接偏好优化（编辑初稿）',
  };
  const title = titles[paper.slug] || paper.title;
  const description = `${paper.englishTitle}（${paper.year}）中文学习笔记。${paper.contribution}${paper.problem}阅读 kk 已发表的原文解读，查看论文来源，并沿时间线继续学习。`;
  const meta = pageMetadata(title, description, `/classics/${paper.slug}`);
  return { ...meta, authors: [{name:'kk', url:absoluteUrl('/about#author')}],
    robots: paper.status === 'draft' ? {index:false,follow:true} : {index:true,follow:true},
    openGraph: {...meta.openGraph, type:'article', authors:[absoluteUrl('/about#author')],
      ...(paper.publication ? {publishedTime:paper.publication.dates[0]+'T00:00:00+08:00'} : {}),
      ...(paper.status === 'archived' ? {images:[{url:absoluteUrl(`/papers/archive/${paper.slug}-01.png`),alt:paper.title}]} : {})} };
}
export function articleSchema(paper: Classic) {
  const url=absoluteUrl(`/classics/${paper.slug}`);
  return { '@context':'https://schema.org', '@type':'BlogPosting', '@id':url+'#article', url,
    mainEntityOfPage:url, headline:paper.title, description:paper.contribution, inLanguage:'zh-CN',
    author:{'@type':'Person',name:'kk',url:absoluteUrl('/about#author')},
    publisher:{'@type':'Organization',name:SITE_NAME,url:SITE_URL},
    ...(paper.publication ? {datePublished:paper.publication.dates[0]+'T00:00:00+08:00'} : {}),
    ...(paper.status === 'archived' ? {image:[absoluteUrl(`/papers/archive/${paper.slug}-01.png`)]} : {}),
    citation:paper.source, about:{'@type':'ScholarlyArticle',name:paper.englishTitle,url:paper.source} };
}
export function breadcrumbSchema(title:string,path:string) {
  return {'@context':'https://schema.org','@type':'BreadcrumbList',itemListElement:[
    {'@type':'ListItem',position:1,name:'首页',item:absoluteUrl('/')},
    {'@type':'ListItem',position:2,name:'经典论文路线',item:absoluteUrl('/timeline')},
    {'@type':'ListItem',position:3,name:title,item:absoluteUrl(path)}]};
}
