import { getPreferredStore, subscribeStoreChanges } from '@/utils/pageStores';
import { useSyncExternalStore } from 'react';

export default function usePreferredStore(userId?: number) {
  return useSyncExternalStore(
    subscribeStoreChanges,
    () => (userId === undefined ? undefined : getPreferredStore(userId)),
    () => undefined,
  );
}
