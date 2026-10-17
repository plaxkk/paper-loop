import { History } from '@/components/history';
import { Footer } from '@/components/footer';
export const metadata={title:'阅读历史',robots:{index:false,follow:false}};
export default function Page(){return <><main id="main" className="shell page-main"><div className="page-heading"><div className="eyebrow">YOUR LIBRARY</div><h1>读到哪里，就从哪里继续。</h1><p>论文、译文和对话，留在当前浏览器的阅读历史里。<br/>服务端保留 30 天；清除 Cookie 后将无法找回。</p></div><History/></main><Footer/></>;}
