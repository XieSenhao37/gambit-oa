import FunctionSearch from '@/components/FunctionSearch';
import GameOrderTodos from '@/components/GameOrderTodos';
import StoreSwitcher from '@/components/StoreSwitcher';
import pages from '@/config/pages.json';
import usePreferredStore from '@/hooks/usePreferredStore';
import { getMe } from '@/services/auth';
import {
  choosePageStore,
  getAllowedPages,
  getPageStores,
  rememberCurrentStore,
  setCurrentStoreId,
} from '@/utils/pageStores';
import { Navigate, Outlet, useLocation, useModel } from '@umijs/max';
import { Result, Tooltip } from 'antd';
import { useEffect, useState } from 'react';
export default function AuthWrapper() {
  const { initialState, setInitialState } = useModel('@@initialState');
  const location = useLocation();
  const auth = initialState?.auth;
  const preferredStore = usePreferredStore(auth?.UserId);
  const page = pages.find((p) => p.path === location.pathname);
  const stores = getPageStores(auth?.Stores ?? [], page?.id ?? '');
  const selected = choosePageStore(stores, preferredStore);
  const contextKey = `${auth?.UserId}:${location.pathname}:${selected?.Id}`;
  const [readyContext, setReadyContext] = useState('');
  useEffect(() => {
    if (selected) {
      setCurrentStoreId(selected.Id);
      // 权限撤销或当前模块不可访问时，切到有权限的门店并全局同步。
      if (auth && page?.scope === 'store') {
        rememberCurrentStore(auth.UserId, selected.Id);
      }
      setReadyContext(contextKey);
    }
  }, [contextKey, selected?.Id, auth?.UserId, page?.scope]);
  useEffect(() => {
    const refresh = () => {
      getMe()
        .then((r) => {
          if (r.Data) setInitialState({ name: r.Data.Name, auth: r.Data });
        })
        .catch(() => {});
    };
    const timer = setInterval(refresh, 30000);
    window.addEventListener('focus', refresh);
    return () => {
      clearInterval(timer);
      window.removeEventListener('focus', refresh);
    };
  }, []);
  if (!localStorage.getItem('token') || !initialState?.auth)
    return <Navigate to="/login" />;
  if (!page || !selected) {
    const allowed = getAllowedPages(auth?.Stores ?? []);
    const first = pages.find((p) => allowed.includes(p.id));
    return first ? (
      <Navigate to={first.path} replace />
    ) : (
      <Result
        status="403"
        title="没有可访问的页面"
        subTitle="请联系总部管理员调整门店及页面授权。"
      />
    );
  }
  // 门店上下文准备好才挂载页面，防止首个请求携带上一页的门店。
  return (
    <>
      <div className="oa-context-bar">
        <div className="oa-context-main">
          <span className="oa-context-path">
            {page.group?.name ? `${page.group.name} / ` : ''}
            <strong>{page.name}</strong>
          </span>
          {page.scope === 'store' &&
            !['dashboard', 'settlement', 'game-community'].includes(
              page.id,
            ) && <StoreSwitcher />}
          {page.scope === 'global' && (
            <Tooltip title="此页配置由所有门店共用，保存会影响全部门店。">
              <span className="oa-scope-label">全门店共享</span>
            </Tooltip>
          )}
          {page.scope === 'admin' && (
            <span className="oa-scope-label">总部管理</span>
          )}
          {page.id === 'game-community' && (
            <span className="oa-scope-label">全部授权门店</span>
          )}
        </div>
        <div className="oa-context-tools">
          <FunctionSearch />
          <GameOrderTodos />
        </div>
      </div>
      <div className="oa-content">
        {readyContext === contextKey && <Outlet key={contextKey} />}
      </div>
    </>
  );
}
