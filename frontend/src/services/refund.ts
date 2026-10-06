import { request } from '@umijs/max';

export async function queryRefundRequests(
  params: API.QueryRefundRequestsParams,
) {
  return request<API.Response<API.PageData<API.RefundRequest>>>(
    '/admin_api/refund/v1/list',
    {
      method: 'GET',
      params,
    },
  );
}

export async function approveRefundRequest(refundRequestId: number) {
  return request<API.Response<unknown>>(
    `/admin_api/refund/v1/approve/${refundRequestId}`,
    {
      method: 'POST',
    },
  );
}

export async function rejectRefundRequest(
  refundRequestId: number,
  data: API.RejectRefundRequestParams,
) {
  return request<API.Response<unknown>>(
    `/admin_api/refund/v1/reject/${refundRequestId}`,
    {
      method: 'POST',
      data,
    },
  );
}
