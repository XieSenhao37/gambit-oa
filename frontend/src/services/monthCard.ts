import { request } from '@umijs/max';

export async function queryMonthCardOrders(
  params: API.QueryMonthCardOrdersParams,
) {
  return request<API.Response<API.PageData<API.MonthCardOrderItem>>>(
    '/admin_api/month-card/v1/orders',
    {
      method: 'GET',
      params,
    },
  );
}

export function getMonthCardConfig() {
  return request<API.Response<{ Price: number; DurationDays: number }>>(
    '/admin_api/month-card/v1/config',
  );
}
export function updateMonthCardConfig(data: {
  Price: number;
  ExpectedPrice: number;
  Note: string;
}) {
  return request('/admin_api/month-card/v1/config', { method: 'POST', data });
}
