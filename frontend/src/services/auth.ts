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
    { skipErrorHandler: true, timeout: 15000 },
  );
export const sendCode = (PhoneNumber: string) =>
  request<API.Response<{ ChallengeId: string; RetryAfter: number }>>(
    '/admin_api/auth/v1/send-code',
    {
      method: 'POST',
      data: { PhoneNumber },
      timeout: 30000,
      skipErrorHandler: true,
    },
  );
export const login = (
  data:
    | { ChallengeId: string; Code: string }
    | { username: string; password: string },
) =>
  request<API.Response<{ token: string }>>('/admin_api/auth/v1/login', {
    method: 'POST',
    data,
    timeout: 20000,
    skipErrorHandler: true,
  });
export const getMe = () =>
  request<API.Response<AuthInfo>>('/admin_api/auth/v1/me');
export const logout = () =>
  request('/admin_api/auth/v1/logout', { method: 'POST' });

/** A transport failure cannot confirm whether a one-time SMS/login request completed. */
export const authResultUncertain = (error: any): boolean =>
  !error?.response && !!error?.request;
export function authErrorMessage(
  error: any,
  operation: 'send' | 'login',
): string {
  const responseMessage = error?.response?.data?.Message;
  if (typeof responseMessage === 'string' && responseMessage)
    return responseMessage;
  if (authResultUncertain(error)) {
    const timedOut = ['ECONNABORTED', 'ETIMEDOUT'].includes(error.code);
    if (operation === 'send')
      return timedOut
        ? '验证码请求超时，发送结果暂未确认，请稍后重新获取'
        : '验证码请求连接中断，发送结果暂未确认，请稍后重新获取';
    return timedOut ? '登录请求超时，请稍后重试' : '登录连接中断，请稍后重试';
  }
  return operation === 'send'
    ? '获取验证码失败，请稍后重试'
    : '登录失败，请稍后重试';
}
