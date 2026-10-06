import { request } from '@umijs/max';

// 餐饮订单经营概览统计
export async function getCateringOverview(params: API.CateringOverviewParams) {
  return request<API.Response<API.CateringOverview>>(
    '/admin_api/stats/v1/catering/overview',
    {
      method: 'GET',
      params,
    },
  );
}

export async function getOpsOverview(params: API.StatsOverviewParams) {
  return request<API.Response<API.OpsOverview>>(
    '/admin_api/stats/v1/ops/overview',
    {
      method: 'GET',
      params,
    },
  );
}

export async function getPlayOverview(params: API.StatsOverviewParams) {
  return request<API.Response<API.PlayOverview>>(
    '/admin_api/stats/v1/play/overview',
    {
      method: 'GET',
      params,
    },
  );
}

export async function getUserOverview(params: API.StatsOverviewParams) {
  return request<API.Response<API.UserOverview>>(
    '/admin_api/stats/v1/user/overview',
    {
      method: 'GET',
      params,
    },
  );
}

export async function getCouponOverview(params: API.StatsOverviewParams) {
  return request<API.Response<API.CouponOverview>>(
    '/admin_api/stats/v1/coupon/overview',
    {
      method: 'GET',
      params,
    },
  );
}

export async function getReferralOverview(params: API.StatsOverviewParams) {
  return request<API.Response<API.ReferralOverview>>(
    '/admin_api/stats/v1/referral/overview',
    {
      method: 'GET',
      params,
    },
  );
}

export async function getMembershipOverview(params: API.StatsOverviewParams) {
  return request<API.Response<API.MembershipOverview>>(
    '/admin_api/stats/v1/membership/overview',
    {
      method: 'GET',
      params,
    },
  );
}

export async function getWalletOverview(params: API.StatsOverviewParams) {
  return request<API.Response<API.WalletOverview>>(
    '/admin_api/stats/v1/wallet/overview',
    {
      method: 'GET',
      params,
    },
  );
}

export async function getPointOverview(params: API.StatsOverviewParams) {
  return request<API.Response<API.PointOverview>>(
    '/admin_api/stats/v1/point/overview',
    {
      method: 'GET',
      params,
    },
  );
}

export async function getUserInsights(
  params: API.StatsOverviewParams & { Limit?: number },
) {
  return request<API.Response<API.UserInsights>>(
    '/admin_api/stats/v1/user/insights',
    {
      method: 'GET',
      params,
    },
  );
}
