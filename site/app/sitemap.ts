import type { MetadataRoute } from 'next';
import { classics } from '@/lib/classics';
import { absoluteUrl } from '@/lib/seo';
export default function sitemap(): MetadataRoute.Sitemap {
  return [ ...['/','/timeline','/workspace','/about','/privacy'].map(path=>({url:absoluteUrl(path)})),
    ...classics().filter(p=>p.status!=='draft').map(p=>({url:absoluteUrl('/classics/'+p.slug)})) ];
}
