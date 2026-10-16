import type { Metadata } from 'next';
import '@fontsource-variable/geist';
import 'katex/dist/katex.min.css';
import './globals.css';
import { Header } from '@/components/header';
export const metadata: Metadata={title:{default:'Paper Loop · 读懂论文，连接脉络',template:'%s · Paper Loop'},description:'沿时间线理解大模型经典论文，用中文解读、原文翻译和有据可查的 AI 对话，读懂自己的论文。'};
export default function RootLayout({children}:{children:React.ReactNode}){ return <html lang="zh-CN" suppressHydrationWarning><body><a href="#main" className="skip-link">跳转到主要内容</a><Header/>{children}</body></html>; }
