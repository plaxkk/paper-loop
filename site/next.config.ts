import type { NextConfig } from 'next';
const config: NextConfig = {
  ...(process.env.VERCEL ? {} : { output: 'standalone' as const }),
  outputFileTracingIncludes: { '/classics/*': ['./content/classics/**/*.md'] },
  experimental: { proxyClientMaxBodySize: '32mb', proxyTimeout: 120000 },
  async redirects() {
    // The platform routes /api/* directly to FastAPI before Next.js. Keep that
    // origin available for the existing authenticated background dispatcher.
    return [{ source: '/:path((?!api(?:/|$)).*)', has: [{ type: 'host' as const, value: 'paper-loop-xi.vercel.app' }],
      destination: 'https://paper-loop.kkplayit.online/:path*', permanent: true }];
  },
  async rewrites() {
    const backend=process.env.PAPER_API_URL || (process.env.VERCEL ? '' : 'http://127.0.0.1:8000');
    if(backend){
      const url=new URL(backend);
      if(process.env.VERCEL && (url.protocol!=='https:' || ['localhost','127.0.0.1','::1','[::1]'].includes(url.hostname))){
        throw new Error('Vercel requires a public HTTPS PAPER_API_URL.');
      }
    }
    return { beforeFiles: backend ? [{ source: '/api/:path*', destination: `${backend.replace(/\/$/,'')}/api/:path*` }] : [] };
  },
  async headers() {
    return [{ source: '/:path*', headers: [
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'Referrer-Policy', value: 'same-origin' },
      { key: 'X-Frame-Options', value: 'DENY' },
      { key: 'Content-Security-Policy', value: "frame-ancestors 'none'; object-src 'none'; base-uri 'self'" },
    ] }];
  },
};
export default config;
