import { Workbench } from '@/components/workbench';
export const metadata={title:'论文阅读工作台',robots:{index:false,follow:false}};
export default async function Page({params}:{params:Promise<{id:string}>}){return <Workbench id={(await params).id}/>;}
