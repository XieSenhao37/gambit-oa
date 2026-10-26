import type { AuthInfo } from '@/services/auth';

type Store = AuthInfo['Stores'][number];
// 当前标签页的有效请求上下文，在挂载业务内容前由权限包装器设置。
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
const preferenceKey = (userId: number) => `oa_current_store:${userId}`;
const listeners = new Set<() => void>();
export const subscribeStoreChanges = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};
export const getPreferredStore = (userId: number) =>
  Number(sessionStorage.getItem(preferenceKey(userId))) || undefined;
export const rememberCurrentStore = (userId: number, id: number) => {
  if (getPreferredStore(userId) === id) return;
  sessionStorage.setItem(preferenceKey(userId), String(id));
  listeners.forEach((listener) => listener());
};
