import { request } from '@umijs/max';

export async function queryStores() {
  return request<API.Response<{ Items: API.StoreInfo[] }>>(
    '/admin_api/store/v1/list',
    {
      method: 'GET',
    },
  );
}
