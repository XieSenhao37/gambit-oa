import { request } from '@umijs/max';

// 查询订单列表
export async function queryOrders(params: API.QueryOrdersParams) {
  return request<API.Response<API.PageData<API.PlayOrder>>>(
    '/admin_api/order/v1/list',
    {
      method: 'GET',
      params,
    },
  );
}

export async function queryPlayWorkbench() {
  return request<API.Response<API.PlayWorkbenchData>>(
    '/admin_api/order/v1/workbench',
    {
      method: 'GET',
    },
  );
}

export async function settlePlayWorkbenchOrder(
  orderId: number,
  data: API.SettlePlayWorkbenchRequest,
) {
  return request<API.Response<API.SettlePlayWorkbenchResult>>(
    `/admin_api/order/v1/workbench/settle/${orderId}`,
    {
      method: 'POST',
      data,
    },
  );
}

export async function quickSettlePlayWorkbenchOrder(orderId: number) {
  return request<API.Response<API.SettlePlayWorkbenchResult>>(
    `/admin_api/order/v1/workbench/quick-settle/${orderId}`,
    {
      method: 'POST',
    },
  );
}
