import { getCurrentStoreId, rememberPageStore } from '@/utils/pageStores';
import { visitGameTodo } from '@/utils/visitGameTodo';
import {
  ArrowRightOutlined,
  CheckCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { history, useModel } from '@umijs/max';
import { Button, Skeleton, Tag } from 'antd';

export default function TodayTodos() {
  const { initialState } = useModel('@@initialState');
  const { allowed, data, error, busy, refresh } = useModel('gameTodos');
  const auth = initialState?.auth;
  if (!allowed) return null;
  const currentStore = auth?.Stores.find(
    (store) => store.Id === getCurrentStoreId(),
  );
  const canVisitCurrent = currentStore?.Pages.includes('game-service-orders');
  const visitFilter = (status: string) => {
    if (!auth || !canVisitCurrent) return;
    rememberPageStore(auth.UserId, 'game-service-orders', getCurrentStoreId());
    history.push(`/game-service-orders?status=${status}`);
  };
  return (
    <section className="oa-panel oa-today-todos" aria-label="租售待办">
      <div className="oa-section-heading">
        <div>
          <h3>
            租售待办{' '}
            {data && <span className="oa-todo-total">{data.Total}</span>}
          </h3>
          <span className="oa-secondary">全部授权门店</span>
        </div>
        <Button
          type="text"
          icon={<ReloadOutlined />}
          loading={busy}
          onClick={() => void refresh()}
        >
          刷新
        </Button>
      </div>
      {canVisitCurrent && (
        <div
          className="oa-todo-filters"
          aria-label={`${currentStore?.Name}快捷筛选`}
        >
          <span className="oa-secondary">{currentStore?.Name}</span>
          {[
            ['待确认', 'pending_confirmation'],
            ['待交付', 'accepted'],
            ['归还待处理', 'return_requested'],
            ['退款待处理', 'refund_attention'],
          ].map(([label, status]) => (
            <Button key={status} onClick={() => visitFilter(status)}>
              {label}
            </Button>
          ))}
          <Button type="link" onClick={() => visitFilter('')}>
            全部订单 <ArrowRightOutlined />
          </Button>
        </div>
      )}
      {error ? (
        <div className="oa-todo-error">待办暂未更新，请刷新后核对。</div>
      ) : !data ? (
        <Skeleton active={false} paragraph={{ rows: 2 }} title={false} />
      ) : !data.Items.length ? (
        <div className="oa-todo-clear">
          <CheckCircleOutlined /> 当前没有需要处理的租售订单
        </div>
      ) : (
        <div className="oa-todo-list">
          {data.Items.slice(0, 4).map((item) => (
            <button
              key={`${item.StoreID}:${item.ID}`}
              type="button"
              className="oa-todo-item"
              onClick={() => visitGameTodo(auth, item)}
            >
              <Tag>{item.Label}</Tag>
              <span className="oa-todo-game">{item.Games || '桌游订单'}</span>
              <span className="oa-secondary">
                {item.StoreName} · #{item.ID}
              </span>
              <ArrowRightOutlined />
            </button>
          ))}
        </div>
      )}
      {data && data.Total > 4 && (
        <div className="oa-todo-more oa-secondary">
          展示最近 4 单，右上角待办可查看其他订单。
        </div>
      )}
    </section>
  );
}
