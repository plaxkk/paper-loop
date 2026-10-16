import { cpSync } from 'node:fs';
import { spawn } from 'node:child_process';
cpSync('public','.next/standalone/public',{recursive:true});
cpSync('content','.next/standalone/content',{recursive:true});
cpSync('.next/static','.next/standalone/.next/static',{recursive:true});
const child=spawn(process.execPath,['.next/standalone/server.js'],{stdio:'inherit',env:{...process.env,HOSTNAME:'0.0.0.0'}});
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>child.kill(signal));
child.on('exit',code=>process.exit(code??0));
