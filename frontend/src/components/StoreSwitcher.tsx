import pages from '@/config/pages.json';
import {
  getCurrentStoreId,
  getPageStores,
  rememberPageStore,
} from '@/utils/pageStores';
import { useLocation, useModel } from '@umijs/max';
import { Select } from 'antd';
import type { CSSProperties } from 'react';
export { getCurrentStoreId } from '@/utils/pageStores';

interface StoreSwitcherProps {
  label?: string;
  size?: 'small' | 'middle' | 'large';
  style?: CSSProperties;
  selectStyle?: CSSProperties;
  onChange?: (storeId: number) => void;
}
export default function StoreSwitcher({
  label = '当前门店',
  size = 'middle',
  style,
  selectStyle,
}: StoreSwitcherProps) {
  const { initialState } = useModel('@@initialState');
  const { pathname } = useLocation();
  const auth = initialState?.auth;
  const page = pages.find((p) => p.path === pathname);
  if (!auth || !page || page.scope !== 'store') return null;
  const stores = getPageStores(auth.Stores, page.id);
  if (!stores.length) return null;
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        flexWrap: 'wrap',
        ...style,
      }}
    >
      <span style={{ flex: '0 0 auto', color: 'rgba(0,0,0,.65)' }}>
        {label}
      </span>
      {stores.length === 1 ? (
        <strong>{stores[0].Name}</strong>
      ) : (
        <Select
          aria-label={label}
          value={getCurrentStoreId()}
          size={size}
          style={{ minWidth: 160, maxWidth: '100%', ...selectStyle }}
          options={stores.map((store) => ({
            label: store.Name,
            value: store.Id,
          }))}
          onChange={(id) => {
            rememberPageStore(auth.UserId, page.id, id);
            // 完整重载，丢弃旧门店的表单、弹窗与进行中的请求。
            window.location.reload();
          }}
        />
      )}
    </div>
  );
}
