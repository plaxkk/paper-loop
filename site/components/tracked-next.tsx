'use client';
import Link from 'next/link';
import { track } from '@/lib/api';
export function TrackedNext({href,children}:{href:string;children:React.ReactNode}){return <Link href={href} onClick={()=>track('classic_next')}>{children}</Link>;}
