import { request } from '@umijs/max';

// 积分商品分类
export async function queryPointCategories() {
  return request<API.Response<API.PointCategoryListData>>(
    '/admin_api/point/v1/categories',
    {
      method: 'GET',
    },
  );
}

export async function createPointCategory(data: API.SavePointCategoryParams) {
  return request<API.Response<API.PointCategoryItem>>(
    '/admin_api/point/v1/categories',
    {
      method: 'POST',
      data,
    },
  );
}

export async function updatePointCategory(
  categoryId: number,
  data: API.SavePointCategoryParams,
) {
  return request<API.Response<API.PointCategoryItem>>(
    `/admin_api/point/v1/categories/${categoryId}`,
    {
      method: 'PUT',
      data,
    },
  );
}

export async function updatePointCategoryStatus(
  categoryId: number,
  data: API.UpdatePointStatusParams,
) {
  return request<API.Response<API.PointCategoryItem>>(
    `/admin_api/point/v1/categories/${categoryId}/status`,
    {
      method: 'PATCH',
      data,
    },
  );
}

export async function deletePointCategory(categoryId: number) {
  return request<API.Response<null>>(
    `/admin_api/point/v1/categories/${categoryId}`,
    {
      method: 'DELETE',
    },
  );
}

// 积分商品
export async function queryPointProducts(params: API.QueryPointProductsParams) {
  return request<API.Response<API.PointProductListData>>(
    '/admin_api/point/v1/products',
    {
      method: 'GET',
      params,
    },
  );
}

export async function createPointProduct(formData: FormData) {
  return request<API.Response<API.PointProductItem>>(
    '/admin_api/point/v1/products',
    {
      method: 'POST',
      data: formData,
    },
  );
}

export async function updatePointProduct(
  productId: number,
  formData: FormData,
) {
  return request<API.Response<API.PointProductItem>>(
    `/admin_api/point/v1/products/${productId}`,
    {
      method: 'PUT',
      data: formData,
    },
  );
}

export async function updatePointProductStatus(
  productId: number,
  data: API.UpdatePointStatusParams,
) {
  return request<API.Response<API.PointProductItem>>(
    `/admin_api/point/v1/products/${productId}/status`,
    {
      method: 'PATCH',
      data,
    },
  );
}

export async function deletePointProduct(productId: number) {
  return request<API.Response<null>>(
    `/admin_api/point/v1/products/${productId}`,
    {
      method: 'DELETE',
    },
  );
}

// 积分提取审计
export async function queryPointWithdraws(
  params: API.QueryPointWithdrawsParams,
) {
  return request<API.Response<API.PointWithdrawListData>>(
    '/admin_api/point/v1/withdraws',
    {
      method: 'GET',
      params,
    },
  );
}

// 积分兑换明细
export async function queryPointRedeemOrders(
  params: API.QueryPointRedeemOrdersParams,
) {
  return request<API.Response<API.PointRedeemOrderListData>>(
    '/admin_api/point/v1/redeem-orders',
    {
      method: 'GET',
      params,
    },
  );
}

// 积分规则配置
export async function getPointConfig() {
  return request<API.Response<API.PointConfig>>('/admin_api/point/v1/config', {
    method: 'GET',
  });
}

export async function updatePointConfig(data: API.PointConfig) {
  return request<API.Response<API.PointConfig>>('/admin_api/point/v1/config', {
    method: 'PUT',
    data,
  });
}
