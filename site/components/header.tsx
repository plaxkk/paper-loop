'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { Icon } from './icons';
export function Header() {
  const path=usePathname();
  const [dark,setDark]=useState(false);
  const [menu,setMenu]=useState(false);
  useEffect(()=>{ const mode=localStorage.getItem('paper-theme'); const value=mode ? mode==='dark' : matchMedia('(prefers-color-scheme: dark)').matches; document.documentElement.dataset.theme=value?'dark':'light'; setDark(value); },[]);
  function toggle(){ const next=!dark; setDark(next); document.documentElement.dataset.theme=next?'dark':'light'; localStorage.setItem('paper-theme',next?'dark':'light'); }
  return <header className="site-header"><div className="header-inner"><Link href="/" className="brand" aria-label="Paper Loop 首页"><span className="brand-mark"><Icon name="book" size={21}/></span><span>Paper Loop<span className="brand-dot">.</span></span></Link><span className="brand-note">读懂论文，连接脉络</span><nav className={menu?'nav open':'nav'} aria-label="主导航">{[['/timeline','经典路线'],['/workspace','论文工作台'],['/history','阅读历史']].map(([href,label])=><Link key={href} className={path.startsWith(href)?'active':''} href={href} onClick={()=>setMenu(false)}>{label}</Link>)}</nav><div className="header-actions"><button className="icon-button" onClick={toggle} aria-label={dark?'切换浅色模式':'切换深色模式'}><Icon name={dark?'sun':'moon'} size={19}/></button><button className="icon-button mobile-menu" onClick={()=>setMenu(!menu)} aria-label="展开导航" aria-expanded={menu}><Icon name="menu"/></button><Link href="/workspace" className="button small header-cta">开始读论文<Icon name="external" size={15}/></Link></div></div></header>;
}
