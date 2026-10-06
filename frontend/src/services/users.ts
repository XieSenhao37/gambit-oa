import { request } from '@umijs/max';

// 查询用户列表
export async function queryUsers(params: API.QueryUsersParams) {
  return request<API.Response<API.PageData<API.UserInfo>>>(
    '/admin_api/user/v1/list',
    {
      method: 'GET',
      skipErrorHandler: true,
      params,
    },
  );
}

// 更新用户
export async function updateUser(userId: number, data: API.UpdateUserRequest) {
  return request<API.Response<null>>(`/admin_api/user/v1/${userId}`, {
    method: 'PUT',
    data,
  });
}
