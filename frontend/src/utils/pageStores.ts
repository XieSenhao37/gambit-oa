import type { AuthInfo } from '@/services/auth';

type Store = AuthInfo['Stores'][number];
// 当前标签页的请求上下文。不能读取其他标签页写入的全局门店值。
let activeStoreId = 1;
export const getCurrentStoreId = () => activeStoreId;
export const setCurrentStoreId = (id: number) => {
  activeStoreId = id;
};
export const getPageStores = (stores: Store[], pageId: string) =>
  stores.filter((store) => store.Pages.includes(pageId));
export const getAllowedPages = (stores: Store[]) => [
  ...new Set(stores.flatMap((store) => store.Pages)),
];
export const choosePageStore = (stores: Store[], preferred?: number) =>
  stores.find((store) => store.Id === preferred) ?? stores[0];
const preferenceKey = (userId: number, pageId: string) =>
  `oa_page_store:${userId}:${pageId}`;
export const getPreferredStore = (userId: number, pageId: string) =>
  Number(sessionStorage.getItem(preferenceKey(userId, pageId))) || undefined;
export const rememberPageStore = (userId: number, pageId: string, id: number) =>
  sessionStorage.setItem(preferenceKey(userId, pageId), String(id));
