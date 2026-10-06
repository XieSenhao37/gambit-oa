import { request, type RequestOptions } from '@umijs/max';

export interface HomeBanner {
  Id: string;
  Title: string;
  Img: string;
  Preview: string;
  Action: 'preview' | 'page' | 'none';
  Page: string;
  Sort: number;
  Enabled: boolean;
}
export interface BannerConfig {
  Items: HomeBanner[];
  Revision: string;
  Migrated: boolean;
}
const endpoint = '/admin_api/banner/v1';
async function call<T>(url: string, options?: RequestOptions): Promise<T> {
  const res = await request<{ Code: number; Message?: string; Data: T }>(url, {
    ...options,
    getResponse: false,
  });
  if (res.Code !== 0) throw new Error(res.Message || '请求失败');
  return res.Data;
}
export const getBanners = () => call<BannerConfig>(endpoint);
export const saveBanners = (Items: HomeBanner[], Revision: string) =>
  call<BannerConfig>(endpoint, { method: 'PUT', data: { Items, Revision } });
export const uploadBanner = (file: File) => {
  const data = new FormData();
  data.append('File', file);
  return call<{ Url: string }>(endpoint + '/image', { method: 'POST', data });
};
// 历史图片仍使用原云存储文件，不重复上传、不改变小程序中的文件 ID。
export function bannerPreviewUrl(url?: string) {
  if (!url?.startsWith('cloud://')) return url || '';
  const match = /^cloud:\/\/[^.]+\.([^/]+)\/(.+)$/.exec(url);
  return match ? `https://${match[1]}.tcb.qcloud.la/${match[2]}` : '';
}

// 支持直接粘贴小程序路径，补齐开头斜杠并保留查询参数。
export function normalizeBannerPage(value: unknown): string {
  if (typeof value !== 'string') return '';
  const page = value.trim();
  const normalized = page.startsWith('/') ? page : `/${page}`;
  if (
    normalized.length > 2048 ||
    /[\s\u0000-\u001f\u007f\\#]/.test(normalized) ||
    !/^\/(?:[a-zA-Z0-9_-]+\/)+[a-zA-Z0-9_-]+(?:\?[^#]*)?$/.test(normalized)
  )
    return '';
  return normalized;
}
