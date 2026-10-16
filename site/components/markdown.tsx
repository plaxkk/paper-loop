import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
export function headingId(text:string){ return text.replace(/\\([\*_`\[\]])/g,'$1').trim().replace(/\s+/g,'-'); }
export function Markdown({children}:{children:string}) { return <ReactMarkdown remarkPlugins={[remarkGfm,remarkMath]} rehypePlugins={[rehypeKatex]} components={{ img:({src,alt})=><img src={src} alt={alt||''} loading="lazy" decoding="async"/>, h2:({children})=><h2 id={headingId(String(children))}>{children}</h2>, a:({href,children})=><a href={href} target={href?.startsWith('http')?'_blank':undefined} rel="noreferrer">{children}</a> }}>{children}</ReactMarkdown>; }
