import type { GameTodo } from '@/models/gameTodos';
import { visitGameTodo } from '@/utils/visitGameTodo';
import { BellOutlined } from '@ant-design/icons';
import { useModel } from '@umijs/max';
import { Badge, Button, Empty, List, Popover, Spin, Typography } from 'antd';
import { useState } from 'react';

export default function GameOrderTodos() {
  const { initialState } = useModel('@@initialState');
  const { allowed, data, error, busy, refresh } = useModel('gameTodos');
  const [open, setOpen] = useState(false);
  if (!allowed) return null;
  const visit = (item: GameTodo) => visitGameTodo(initialState?.auth, item);
  return (
    <Popover
      trigger="click"
      placement="bottomRight"
      open={open}
      onOpenChange={(value) => {
        setOpen(value);
        if (value) void refresh();
      }}
      title={
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>订单待办{data ? ` · ${data.Total}` : ''}</span>
          <Button
            type="text"
            size="small"
            loading={busy}
            onClick={() => void refresh()}
          >
            刷新
          </Button>
        </div>
      }
      content={
        <div
          style={{
            width: 340,
            maxWidth: '80vw',
            maxHeight: 420,
            overflowY: 'auto',
          }}
        >
          {error ? (
            <Typography.Text type="secondary">
              待办暂未更新，请点击刷新。
            </Typography.Text>
          ) : !data ? (
            <Spin />
          ) : (
            <>
              <List<GameTodo>
                dataSource={data.Items}
                locale={{
                  emptyText: (
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description="暂无待办"
                    />
                  ),
                }}
                renderItem={(item) => (
                  <List.Item style={{ padding: 0 }}>
                    <button
                      type="button"
                      onClick={() => visit(item)}
                      style={{
                        width: '100%',
                        textAlign: 'left',
                        cursor: 'pointer',
                        background: 'transparent',
                        border: 0,
                        padding: '14px 4px',
                        color: '#202124',
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          gap: 12,
                          marginBottom: 6,
                        }}
                      >
                        <strong>{item.Label}</strong>
                        <span style={{ color: '#707782' }}>
                          {item.StoreName} · #{item.ID}
                        </span>
                      </div>
                      <Typography.Text ellipsis style={{ maxWidth: 312 }}>
                        {item.Games || '桌游订单'}
                      </Typography.Text>
                    </button>
                  </List.Item>
                )}
              />
              {data.Total > data.Items.length && (
                <Typography.Text type="secondary">
                  展示最近30条，更多请到租售订单查看。
                </Typography.Text>
              )}
            </>
          )}
        </div>
      }
    >
      <Button
        type="text"
        aria-label={error ? '订单待办暂未更新' : `订单待办${data?.Total ?? ''}`}
        style={{ height: 44 }}
      >
        <Badge count={error ? '!' : data?.Total} size="small" offset={[5, -2]}>
          <BellOutlined style={{ fontSize: 18 }} />
        </Badge>
        <span style={{ marginLeft: 10 }}>待办</span>
      </Button>
    </Popover>
  );
}
