import { request } from '@umijs/max';

// 查询桌游列表
export async function queryGames(params: API.QueryGamesParams) {
  return request<API.Response<API.PageData<API.BoardGame>>>(
    '/admin_api/game/v1/inventory/list',
    {
      method: 'GET',
      params,
    },
  );
}

export async function queryGameLibrary(params: API.QueryGamesParams) {
  return request<API.Response<API.PageData<API.BoardGame>>>(
    '/admin_api/game/v1/library/list',
    {
      method: 'GET',
      params,
    },
  );
}

export async function getGameLibraryItem(id: number) {
  return request<API.Response<API.BoardGame>>(
    `/admin_api/game/v1/library/${id}`,
    {
      method: 'GET',
    },
  );
}

export async function createGameLibraryItem(params: FormData) {
  return request<API.Response<API.BoardGame>>('/admin_api/game/v1/library', {
    method: 'POST',
    // 图片在服务端上传 COS 后才保存，单独设置等待时间。
    timeout: 120000,
    data: params,
  });
}

export async function updateGameLibraryItem(id: number, params: FormData) {
  return request<API.Response<API.BoardGame>>(
    `/admin_api/game/v1/library/${id}`,
    {
      method: 'PUT',
      timeout: 120000,
      data: params,
    },
  );
}

export async function deleteGameLibraryItem(id: number) {
  return request<API.Response<null>>(`/admin_api/game/v1/${id}`, {
    method: 'DELETE',
  });
}

export async function addGameInventory(params: API.SaveGameInventoryParams) {
  return request<API.Response<API.BoardGame>>('/admin_api/game/v1/inventory', {
    method: 'POST',
    data: params,
  });
}

export async function updateGameInventory(
  id: number,
  params: API.UpdateGameInventoryParams,
) {
  return request<API.Response<API.BoardGame>>(
    `/admin_api/game/v1/inventory/${id}`,
    {
      method: 'PUT',
      data: params,
    },
  );
}

export async function deleteGameInventory(id: number) {
  return request<API.Response<null>>(`/admin_api/game/v1/inventory/${id}`, {
    method: 'DELETE',
  });
}

export async function uploadGameImage(
  file: File,
  signal: AbortSignal,
  onProgress: (percent: number) => void,
) {
  const data = new FormData();
  data.append('Image', file);
  return request<API.Response<{ Url: string }>>(
    '/admin_api/game/v1/library/image',
    {
      method: 'POST',
      data,
      signal,
      timeout: 120000,
      onUploadProgress: (event: { loaded: number; total?: number }) => {
        if (event.total)
          onProgress(Math.min(95, 10 + (event.loaded / event.total) * 85));
      },
    },
  );
}
