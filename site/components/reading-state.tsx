'use client';
import { useEffect,useState } from 'react';
import { track } from '@/lib/api';
import { Icon } from './icons';
export function ReadState({slug,button=false}:{slug:string;button?:boolean}){
  const [read,setRead]=useState(false);
  useEffect(()=>{ setRead(localStorage.getItem('classic-read:'+slug)==='true'); if(button)track('classic_open'); },[slug,button]);
  if(!button)return read?<span className="read-badge"><Icon name="check" size={13}/>已读</span>:null;
  return <button className="button secondary" onClick={()=>{localStorage.setItem('classic-read:'+slug,String(!read));setRead(!read);}}><Icon name={read?'check':'book'} size={17}/>{read?'已标记读完':'标记读完'}</button>;
}
