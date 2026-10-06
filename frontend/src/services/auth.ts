import { request } from '@umijs/max';
export interface AuthInfo {
  UserId: number;
  Name: string;
  Headquarters: boolean;
  Stores: { Id: number; Name: string; Role: string; Pages: string[] }[];
  Pages: { id: string; name: string; path: string; scope: string }[];
}
export const authStatus = () =>
  request<API.Response<{ SmsReady: boolean; LoginMode: 'password' | 'sms' }>>(
    '/admin_api/auth/v1/status',
  );
export const sendCode = (PhoneNumber: string) =>
  request<API.Response<{ ChallengeId: string; RetryAfter: number }>>(
    '/admin_api/auth/v1/send-code',
    { method: 'POST', data: { PhoneNumber } },
  );
export const login = (
  data:
    | { ChallengeId: string; Code: string }
    | { username: string; password: string },
) =>
  request<API.Response<{ token: string }>>('/admin_api/auth/v1/login', {
    method: 'POST',
    data,
  });
export const getMe = () =>
  request<API.Response<AuthInfo>>('/admin_api/auth/v1/me');
export const logout = () =>
  request('/admin_api/auth/v1/logout', { method: 'POST' });
