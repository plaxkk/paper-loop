import type { Session } from './types';
let sessionRequest: Promise<Session> | null = null;
export async function session(refresh = false): Promise<Session> {
  if (!sessionRequest || refresh) sessionRequest = request<Session>('/session').catch(error => { sessionRequest = null; throw error; });
  return sessionRequest;
}
async function request<T>(path:string, options:RequestInit = {}): Promise<T> {
  let response: Response;
  try { response = await fetch('/api' + path, { ...options, credentials:'same-origin', cache:'no-store' }); }
  catch { throw new Error('暂时无法连接论文服务，请稍后重试。'); }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : '请求未能完成，请稍后重试。');
  return body as T;
}
export async function api<T>(path:string, options:RequestInit = {}): Promise<T> {
  await session();
  return request<T>(path, options);
}
export const jsonBody = (value:unknown, method = 'POST'): RequestInit => ({ method, headers:{'Content-Type':'application/json'}, body:JSON.stringify(value) });
export function track(kind:string, workspace?:string, category = '') {
  void api('/events', {...jsonBody({kind, workspace, category}),keepalive:true}).catch(() => {});
}
