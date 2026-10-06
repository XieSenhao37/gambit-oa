import { request } from '@umijs/max';

export async function queryCateringOrders(
  params: API.QueryCateringOrdersParams,
) {
  return request<API.Response<API.PageData<API.CateringOrder>>>(
    '/admin_api/catering/v1/list',
    {
      method: 'GET',
      params,
    },
  );
}

export async function queryCateringOrderHistory(
  params: API.QueryCateringHistoryParams,
) {
  return request<API.Response<API.PageData<API.CateringOrder>>>(
    '/admin_api/catering/v1/history',
    {
      method: 'GET',
      params,
    },
  );
}

export async function finishCateringOrder(cateringId: number) {
  return request<API.Response<API.FinishCateringOrderResult>>(
    `/admin_api/catering/v1/finish/${cateringId}`,
    {
      method: 'POST',
    },
  );
}

export async function completeCateringOrder(cateringId: number) {
  return request<API.Response<null>>(
    `/admin_api/catering/v1/complete/${cateringId}`,
    {
      method: 'POST',
    },
  );
}
