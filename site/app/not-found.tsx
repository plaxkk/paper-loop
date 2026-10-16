import Link from 'next/link';
export default function NotFound(){return <main id="main" className="empty-state page-main"><div className="eyebrow">404 / PAGE NOT FOUND</div><h1>这页还没有写下。</h1><p>可以回到经典路线，继续寻找下一篇。</p><Link href="/timeline" className="button">回到经典路线</Link></main>;}
