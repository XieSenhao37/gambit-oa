import { request } from '@umijs/max';
export const settlementGet = (path: string, params?: any) =>
  request<any>(`/admin_api/settlement/v1/${path}`, { params });
export const settlementPost = (path: string, data?: any) =>
  request<any>(`/admin_api/settlement/v1/${path}`, { method: 'POST', data });
export const settlementExport = (params: any) =>
  request<Blob>('/admin_api/settlement/v1/export', {
    params,
    responseType: 'blob',
  });
export const settlementProof = (id: number, kind: 'expenses' = 'expenses') =>
  request<Blob>(`/admin_api/settlement/v1/${kind}/${id}/proof`, {
    responseType: 'blob',
  });
