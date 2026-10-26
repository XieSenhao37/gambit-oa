import type { GameTodo } from '@/models/gameTodos';
import type { AuthInfo } from '@/services/auth';
import { history } from '@umijs/max';
import { rememberCurrentStore } from './pageStores';

export function visitGameTodo(auth: AuthInfo | undefined, item: GameTodo) {
  if (
    !auth?.Stores.some(
      (store) =>
        store.Id === item.StoreID &&
        store.Pages.includes('game-service-orders'),
    )
  )
    return;
  rememberCurrentStore(auth.UserId, item.StoreID);
  history.push(`/game-service-orders?orderId=${item.ID}`);
}
