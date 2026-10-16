'use client';
export default function ErrorPage({reset}:{reset:()=>void}){return <main id="main" className="empty-state page-main"><h1>这一页暂时未能打开。</h1><p>请重试。已有论文与对话不会因此删除。</p><button className="button" onClick={reset}>重新加载</button></main>;}
