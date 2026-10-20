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
    { skipErrorHandler: true },
  );
}
export function updateMonthCardConfig(data: {
  Price: number;
  ExpectedPrice: number;
  Note: string;
}) {
  return request('/admin_api/month-card/v1/config', { method: 'POST', data });
}

export function manualOpenMonthCards(data: {
  UserIds: number[];
  OpenMonths: number;
  ExpectedPrice: number;
  RequestKey: string;
}) {
  return request<API.Response<{ Items: API.MonthCardOrderItem[] }>>(
    '/admin_api/month-card/v1/manual-open-batch',
    { method: 'POST', data, skipErrorHandler: true },
  );
}
