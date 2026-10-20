import { request, useModel } from '@umijs/max';
import { useCallback, useEffect, useRef, useState } from 'react';

export type GameTodo = {
  ID: number;
  StoreID: number;
  StoreName: string;
  Label: string;
  Games: string;
};
export type GameTodosData = { Total: number; Items: GameTodo[] };

/** Shared by the header and workbench; one polling loop per signed-in account. */
export default function useGameTodos(): {
  allowed: boolean;
  data?: GameTodosData;
  error: boolean;
  busy: boolean;
  refresh: () => Promise<void>;
} {
  const { initialState } = useModel('@@initialState');
  const auth = initialState?.auth;
  const allowed = !!auth?.Stores.some((store) =>
    store.Pages.includes('game-service-orders'),
  );
  const key = JSON.stringify([
    auth?.UserId,
    auth?.Stores.map((store) => [store.Id, store.Pages]),
  ]);
  const identity = useRef(key);
  identity.current = key;
  const mounted = useRef(true);
  const pending = useRef<string>();
  const queued = useRef(false);
  const refreshLatest = useRef<() => void>(() => {});
  const [snapshot, setSnapshot] = useState<{
    key: string;
    data?: GameTodosData;
    error: boolean;
    busy: boolean;
  }>({ key, error: false, busy: false });
  const refresh = useCallback(async () => {
    if (!allowed || document.visibilityState === 'hidden') return;
    if (pending.current === key) {
      queued.current = true;
      return;
    }
    pending.current = key;
    setSnapshot((old) => ({
      key,
      data: old.key === key ? old.data : undefined,
      error: false,
      busy: true,
    }));
    try {
      const response = await request<{ Code: number; Data: GameTodosData }>(
        '/admin_api/game-service/v1/todos',
        { skipErrorHandler: true, timeout: 30000 },
      );
      if (response.Code !== 0) throw Error('unavailable');
      if (mounted.current && identity.current === key)
        setSnapshot({ key, data: response.Data, error: false, busy: false });
    } catch {
      if (mounted.current && identity.current === key)
        setSnapshot((old) => ({ ...old, key, error: true, busy: false }));
    } finally {
      if (pending.current === key) pending.current = undefined;
      if (mounted.current && identity.current === key && queued.current) {
        queued.current = false;
        refreshLatest.current();
      }
    }
  }, [key, allowed]);
  refreshLatest.current = () => {
    void refresh();
  };
  useEffect(() => {
    mounted.current = true;
    void refresh();
    const update = () => void refresh();
    const timer = window.setInterval(update, 60000);
    window.addEventListener('focus', update);
    document.addEventListener('visibilitychange', update);
    window.addEventListener('game-order-updated', update);
    return () => {
      mounted.current = false;
      clearInterval(timer);
      window.removeEventListener('focus', update);
      document.removeEventListener('visibilitychange', update);
      window.removeEventListener('game-order-updated', update);
    };
  }, [refresh]);
  return {
    allowed,
    data: allowed && snapshot.key === key ? snapshot.data : undefined,
    error: allowed && snapshot.key === key && snapshot.error,
    busy: snapshot.key === key && snapshot.busy,
    refresh,
  };
}
