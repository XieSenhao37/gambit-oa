import React from 'react';
// 运行时配置

// 全局初始化数据配置，用于 Layout 用户信息和权限初始化
// 更多信息见文档：https://umijs.org/docs/api/runtime-config#getinitialstate
import { AuthInfo, getMe, logout } from '@/services/auth';
export async function getInitialState(): Promise<{
  name: string;
  auth?: AuthInfo;
}> {
  if (!localStorage.getItem('token')) return { name: '' };
  try {
    const { Data: auth } = await getMe();
    if (!auth) throw Error('身份响应无效');
    return { name: auth.Name, auth };
  } catch {
    localStorage.removeItem('token');
    return { name: '' };
  }
}

import { getGroupedMenuData } from '@/config/menu';
import { getAllowedPages, getCurrentStoreId } from '@/utils/pageStores';
import { LogoutOutlined } from '@ant-design/icons';
import { history, RequestConfig, RuntimeConfig } from '@umijs/max';
import { Button, message } from 'antd';

// 布局配置
export const layout: RuntimeConfig['layout'] = ({ initialState }) => {
  const signOut = async () => {
    try {
      await logout();
    } finally {
      localStorage.removeItem('token');
      localStorage.removeItem('role');
      window.location.href = '/login';
    }
  };
  return {
    logo: '/favicon.ico',
    actionsRender: () => [],
    menuFooterRender: (props) =>
      React.createElement(
        Button,
        {
          type: 'text',
          block: true,
          onClick: signOut,
          icon: React.createElement(LogoutOutlined),
          title: '退出登录',
          'aria-label': '退出登录',
          style: { height: 44, maxWidth: '100%', overflow: 'hidden' },
        },
        props?.collapsed ? null : '退出登录',
      ),
    menu: {
      locale: false,
    },
    menuDataRender: () =>
      getGroupedMenuData(getAllowedPages(initialState?.auth?.Stores ?? [])),
  };
};

// 请求配置
export const request: RequestConfig = {
  timeout: 10000,
  requestInterceptors: [
    (url, options) => {
      const token = localStorage.getItem('token');
      if (token) {
        options.headers = {
          ...options.headers,
          Authorization: `Bearer ${token}`,
          'X-Store-ID': String(getCurrentStoreId()),
        };
      } else {
        options.headers = {
          ...options.headers,
          'X-Store-ID': String(getCurrentStoreId()),
        };
      }
      return { url, options };
    },
  ],
  responseInterceptors: [
    (response) => {
      // 处理 HTTP 状态码
      if (response.status === 401 && window.location.pathname !== '/login') {
        // 清除本地存储的登录信息
        localStorage.removeItem('token');
        localStorage.removeItem('role');

        // 显示提示消息
        sessionStorage.setItem('oa_session_expired', '1');
        message.error({
          content: '登录已过期或已失效，请重新登录',
          key: 'oa-session-expired',
        });

        // 跳转到登录页
        if (window.location.pathname !== '/login') {
          history.replace('/login?reason=expired');
        }
      }
      return response;
    },
  ],
  errorConfig: {
    // 错误处理
    errorHandler: (error: any) => {
      // 处理业务错误码
      if (error.response) {
        // 服务器返回了错误响应
        if (
          error.response.status === 401 &&
          window.location.pathname === '/login'
        ) {
          message.error(
            error.response.data?.Message || '登录失败，请检查登录信息',
          );
        } else if (error.response.status === 401) {
          // 清除本地存储的登录信息
          localStorage.removeItem('token');
          localStorage.removeItem('role');

          // 显示提示消息
          sessionStorage.setItem('oa_session_expired', '1');
          message.error({
            content: '登录已过期或已失效，请重新登录',
            key: 'oa-session-expired',
          });

          // 跳转到登录页
          if (window.location.pathname !== '/login') {
            history.replace('/login?reason=expired');
          }
        } else {
          // 其他错误
          message.error(error.response.data?.Message || '请求失败');
        }
      } else if (error.request) {
        // 请求已发送但没有收到响应
        message.error(
          error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT'
            ? '请求超时，未能确认操作结果。保存操作请先刷新列表核对，避免重复新增。'
            : '连接中断，未能确认操作结果。保存操作请先刷新列表核对，再决定是否重试。',
        );
      } else {
        // 请求设置时出现错误
        message.error('请求错误');
      }
      throw error; // 继续抛出错误
    },
  },
};
