import type { Metadata } from 'next';
import '@fontsource-variable/geist';
import 'katex/dist/katex.min.css';
import './globals.css';
import { Header } from '@/components/header';
import { SITE_URL } from '@/lib/seo';
import { Analytics } from '@vercel/analytics/next';
export const metadata: Metadata={metadataBase:new URL(SITE_URL),title:{default:'AI 经典论文中文解读与大模型学习路线 · Paper Loop',template:'%s · Paper Loop'},description:'阅读 kk 已发表的 AI 经典论文中文解读，沿 Transformer、GPT、BERT、Scaling Laws 到对齐的时间线学习大模型，并在论文工作台导入 PDF 或 arXiv 原文。',verification:{google:'do76pD0ZKrgfDYEjdC6lNMuX1aYWPovcIlYrKTkG0ME',other:{'msvalidate.01':'DE5EBA368085EBACDC37DFE16D13D452','naver-site-verification':['7b65a4867eb668f49d26a81de64670c52e59e0ca','76e5cf39accb21376c236296d987f513ed295264']}},robots:{index:true,follow:true}};
export default function RootLayout({children}:{children:React.ReactNode}){ return <html lang="zh-CN" suppressHydrationWarning><body><a href="#main" className="skip-link">跳转到主要内容</a><Header/>{children}<Analytics/></body></html>; }
