import { request } from '@umijs/max';

export async function queryWalletTiers(params: API.QueryWalletTiersParams) {
  return request<API.Response<API.WalletTierListData>>(
    '/admin_api/wallet/v1/tiers',
    {
      method: 'GET',
      params,
    },
  );
}

export async function createWalletTier(data: API.SaveWalletTierParams) {
  return request<API.Response<API.WalletTierItem>>(
    '/admin_api/wallet/v1/tiers',
    {
      method: 'POST',
      data,
    },
  );
}

export async function updateWalletTier(
  tierId: number,
  data: API.SaveWalletTierParams,
) {
  return request<API.Response<API.WalletTierItem>>(
    `/admin_api/wallet/v1/tiers/${tierId}`,
    {
      method: 'PUT',
      data,
    },
  );
}

export async function updateWalletTierStatus(
  tierId: number,
  data: API.UpdateWalletTierStatusParams,
) {
  return request<API.Response<API.WalletTierItem>>(
    `/admin_api/wallet/v1/tiers/${tierId}/status`,
    {
      method: 'PATCH',
      data,
    },
  );
}

export async function deleteWalletTier(tierId: number) {
  return request<API.Response<null>>(`/admin_api/wallet/v1/tiers/${tierId}`, {
    method: 'DELETE',
  });
}
