import { states, type Order } from '@/services/gameServices';

export function deliveryLabel(method: string, service?: string) {
  if (method !== 'shipping') return '门店自提';
  if (!service) return '快递到付';
  const label = (
    { sf_standard: '普快', sf_express: '特快', sf_local: '同城秒送' } as Record<
      string,
      string
    >
  )[service];
  return `顺丰到付 · ${label || '待确认档位'}`;
}

const listStatuses = [
  'todo',
  '',
  'pending_confirmation',
  'return_requested',
  'due_today',
  'overdue',
  'refund_attention',
  ...Object.keys(states),
];
export function readOrderFilters(search: string) {
  const params = new URLSearchParams(search);
  const status = params.get('status') ?? 'todo';
  const kind = params.get('kind') || '';
  const page = Number(params.get('page') || 1);
  return {
    status: listStatuses.includes(status) ? status : 'todo',
    kind: ['', 'rental', 'purchase', 'buyout'].includes(kind) ? kind : '',
    page: Number.isSafeInteger(page) && page > 0 ? page : 1,
    keyword: params.get('keyword') || '',
  };
}
export function orderAction(order: Pick<Order, 'Kind' | 'Status'>) {
  if (order.Kind === 'buyout') return '';
  if (['pending_confirm', 'pending_accept'].includes(order.Status))
    return 'accept';
  if (order.Status === 'accepted') return 'dispatch';
  if (
    order.Kind === 'rental' &&
    ['rented', 'inspection'].includes(order.Status)
  )
    return 'return_complete';
  return '';
}
export function orderActionLabel(
  order: Pick<Order, 'Kind' | 'Status' | 'DeliveryMethod'>,
) {
  const action = orderAction(order);
  return action === 'accept'
    ? '确认订单'
    : action === 'dispatch'
    ? order.DeliveryMethod === 'shipping'
      ? '登记发货'
      : '确认取货'
    : action === 'return_complete'
    ? '确认归还'
    : '';
}
