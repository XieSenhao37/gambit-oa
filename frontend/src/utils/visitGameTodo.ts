import type { GameTodo } from '@/models/gameTodos';
import type { AuthInfo } from '@/services/auth';
import { rememberPageStore } from './pageStores';

export function visitGameTodo(auth: AuthInfo | undefined, item: GameTodo) {
  if (
    !auth?.Stores.some(
      (store) =>
        store.Id === item.StoreID &&
        store.Pages.includes('game-service-orders'),
    )
  )
    return;
  rememberPageStore(auth.UserId, 'game-service-orders', item.StoreID);
  window.location.assign(`/game-service-orders?orderId=${item.ID}`);
}
