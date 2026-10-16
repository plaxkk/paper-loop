import { NextResponse } from 'next/server';
export const dynamic='force-dynamic';
const detail='论文工作台暂未开放，经典论文栏目可正常阅读。';
type Context={params:Promise<{path:string[]}>};
export async function GET(_request:Request,context:Context){
  const {path}=await context.params;
  if(path.join('/')==='session')return NextResponse.json({service_available:false,ai_available:false,remaining_imports:0,remaining_actions:0,retention_days:30},{headers:{'Cache-Control':'no-store'}});
  return NextResponse.json({detail,code:'PAPER_SERVICE_NOT_CONFIGURED'},{status:503,headers:{'Cache-Control':'no-store'}});
}
export async function POST(){return NextResponse.json({detail,code:'PAPER_SERVICE_NOT_CONFIGURED'},{status:503});}
export const PATCH=POST;
export const DELETE=POST;
