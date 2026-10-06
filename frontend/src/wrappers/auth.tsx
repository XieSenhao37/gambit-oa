import StoreSwitcher from '@/components/StoreSwitcher';
import pages from '@/config/pages.json';
import { getMe } from '@/services/auth';
import {
  choosePageStore,
  getAllowedPages,
  getPageStores,
  getPreferredStore,
  setCurrentStoreId,
} from '@/utils/pageStores';
import { Navigate, Outlet, useLocation, useModel } from '@umijs/max';
import { Alert, Result } from 'antd';
import { useEffect, useState } from 'react';
export default function AuthWrapper() {
  const { initialState, setInitialState } = useModel('@@initialState');
  const location = useLocation();
  const auth = initialState?.auth;
  const page = pages.find((p) => p.path === location.pathname);
  const stores = getPageStores(auth?.Stores ?? [], page?.id ?? '');
  const selected = choosePageStore(
    stores,
    auth && page ? getPreferredStore(auth.UserId, page.id) : undefined,
  );
  const contextKey = `${auth?.UserId}:${location.pathname}:${selected?.Id}`;
  const [readyContext, setReadyContext] = useState('');
  useEffect(() => {
    if (selected) {
      setCurrentStoreId(selected.Id);
      setReadyContext(contextKey);
    }
  }, [contextKey, selected?.Id]);
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
  if (readyContext !== contextKey) return null;
  return (
    <>
      {page.scope === 'store' &&
        !['dashboard', 'settlement'].includes(page.id) && (
          <div
            style={{
              margin: '16px 24px 0',
              padding: '12px 16px',
              background: '#fff',
              borderRadius: 8,
            }}
          >
            <StoreSwitcher />
          </div>
        )}
      {page.scope === 'global' && (
        <Alert
          showIcon
          type="warning"
          message="全品牌共享配置"
          description="此页面的修改影响所有门店，请确认后操作。"
          style={{ margin: 16 }}
        />
      )}
      <Outlet key={contextKey} />
    </>
  );
}
