import { useModel } from '@umijs/max';
import { getCurrentStoreId, getPageStores } from '@/utils/pageStores';
export default function useGameServiceAccess() {
  const { initialState } = useModel('@@initialState');
  const stores = initialState?.auth?.Stores ?? [];
  const allowed = (page: string) =>
    getPageStores(stores, page).some(
      (store) => store.Id === getCurrentStoreId()
    );
  return { canManage: allowed('game-services'), canRefund: allowed('refunds') };
}
