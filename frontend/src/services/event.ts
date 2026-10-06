import { request } from '@umijs/max';
export async function eventAPI(path: string, method = 'GET', data?: any) {
  const res = await request('/admin_api/event/v1/' + path, {
    method,
    ...(method === 'GET' ? { params: data } : { data }),
  });
  if (res.Code !== 0) throw new Error(res.Message || '请求失败');
  return res.Data;
}
