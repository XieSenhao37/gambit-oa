import { request } from '@umijs/max';

export async function queryDishes(params: API.QueryDishesParams) {
  return request<API.Response<API.DishListData>>('/admin_api/dish/v1/list', {
    method: 'GET',
    params,
  });
}

export async function createDish(formData: FormData) {
  return request<API.Response<API.DishItem>>('/admin_api/dish/v1/create', {
    method: 'POST',
    data: formData,
  });
}

export async function updateDish(dishId: number, formData: FormData) {
  return request<API.Response<API.DishItem>>(`/admin_api/dish/v1/${dishId}`, {
    method: 'PUT',
    data: formData,
  });
}

export async function updateDishStatus(
  dishId: number,
  params: API.UpdateDishStatusParams,
) {
  return request<API.Response<API.DishItem>>(
    `/admin_api/dish/v1/${dishId}/status`,
    {
      method: 'PATCH',
      data: params,
    },
  );
}

export async function queryDishLibrary(params: API.QueryDishesParams) {
  return request<API.Response<API.DishLibraryListData>>(
    '/admin_api/dish/v1/library/list',
    {
      method: 'GET',
      params,
    },
  );
}

export async function createDishLibraryItem(formData: FormData) {
  return request<API.Response<API.DishLibraryItem>>(
    '/admin_api/dish/v1/library',
    {
      method: 'POST',
      data: formData,
    },
  );
}

export async function updateDishLibraryItem(
  itemId: number,
  formData: FormData,
) {
  return request<API.Response<API.DishLibraryItem>>(
    `/admin_api/dish/v1/library/${itemId}`,
    {
      method: 'PUT',
      data: formData,
    },
  );
}

export async function deleteDishLibraryItem(itemId: number) {
  return request<API.Response<null>>(`/admin_api/dish/v1/library/${itemId}`, {
    method: 'DELETE',
  });
}

export async function addDishStoreItem(params: API.SaveDishStoreItemParams) {
  return request<API.Response<API.DishItem>>('/admin_api/dish/v1/store-items', {
    method: 'POST',
    data: params,
  });
}

export async function updateDishStoreItem(
  itemId: number,
  params: API.UpdateDishStoreItemParams,
) {
  return request<API.Response<API.DishItem>>(
    `/admin_api/dish/v1/store-items/${itemId}`,
    {
      method: 'PUT',
      data: params,
    },
  );
}

export async function deleteDishStoreItem(itemId: number) {
  return request<API.Response<null>>(
    `/admin_api/dish/v1/store-items/${itemId}`,
    {
      method: 'DELETE',
    },
  );
}
