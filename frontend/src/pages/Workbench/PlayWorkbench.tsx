import {
  queryPlayWorkbench,
  quickSettlePlayWorkbenchOrder,
  settlePlayWorkbenchOrder,
} from '@/services/orders';
import {
  ClockCircleOutlined,
  ReloadOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import {
  Badge,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Row,
  Space,
  Spin,
  Statistic,
  Switch,
  Tag,
  Typography,
} from 'antd';
import dayjs from 'dayjs';
import { useCallback, useEffect, useRef, useState } from 'react';
import styles from './index.less';

const { Text, Title } = Typography;

const formatAmount = (amount: number) => `¥${(amount / 100).toFixed(2)}`;
const formatTime = (timestamp?: number | null) =>
  timestamp ? dayjs(timestamp).format('MM-DD HH:mm') : '—';

const getOrderStatus = (
  order: API.PlayWorkbenchOrder,
): API.PlayWorkbenchStatus => {
  if (order.SettleStatus === 1) {
    return 'settled';
  }
  return order.PaymentPending ? 'payment_pending' : 'pending';
};

const statusMeta: Record<
  API.PlayWorkbenchStatus,
  { color: string; label: string }
> = {
  pending: { color: 'blue', label: '待结算' },
  payment_pending: { color: 'orange', label: '支付中' },
  settled: { color: 'green', label: '已结算' },
};

const RecentSettlementGroups: React.FC<{
  groups: API.PlayWorkbenchRecentGroup[];
  actioningId?: number;
  onManualSettle: (order: API.PlayWorkbenchOrder) => void;
  onQuickSettle: (order: API.PlayWorkbenchOrder) => void;
}> = ({ groups, actioningId, onManualSettle, onQuickSettle }) => {
  if (groups.length === 0) {
    return null;
  }
  return (
    <section aria-label="近五分钟结算核账" className={styles.reconciliation}>
      <div className={styles.sectionHeading}>
        <div>
          <Title level={4}>近 5 分钟结算核账</Title>
          <Text type="secondary">按相近入场时间自动归组，便于核对多人结算</Text>
        </div>
      </div>
      <Space direction="vertical" size="middle" className={styles.groupList}>
        {groups.map((group) => {
          const mismatched =
            group.SettledTotalAmount !== group.TheoreticalTotalAmount;
          return (
            <div className={styles.groupRow} key={group.ID}>
              <Card size="small" className={styles.groupSummary}>
                <Space direction="vertical" size={8}>
                  <Text strong>批次汇总</Text>
                  <div className={styles.summaryGrid}>
                    <Statistic
                      title="订单数"
                      value={group.OrderCount}
                      suffix="单"
                    />
                    <Statistic
                      title="游玩时长"
                      value={
                        group.MinPlayHours === group.MaxPlayHours
                          ? `${group.MinPlayHours} 小时`
                          : `${group.MinPlayHours}–${group.MaxPlayHours} 小时`
                      }
                    />
                    <Statistic
                      title="理论总额"
                      value={formatAmount(group.TheoreticalTotalAmount)}
                    />
                    <Statistic
                      title="当前总额"
                      value={formatAmount(group.SettledTotalAmount)}
                      valueStyle={mismatched ? { color: '#cf1322' } : undefined}
                    />
                  </div>
                  {mismatched && (
                    <Text type="danger" strong>
                      <WarningOutlined /> 当前总额与理论总额不一致
                    </Text>
                  )}
                </Space>
              </Card>
              <div className={styles.groupOrders}>
                {group.Orders.map((order) => {
                  const canSettle = getOrderStatus(order) === 'pending';
                  const isBusy = actioningId !== undefined;
                  return (
                    <Card
                      size="small"
                      className={styles.groupOrderCard}
                      key={order.ID}
                    >
                      <Space direction="vertical" size={8}>
                        <Text strong>
                          {order.NickName || '未设置昵称'} · #
                          {order.UserID || '—'}
                        </Text>
                        <Text type="secondary">
                          {formatTime(order.InTime)} 入场
                        </Text>
                        <Text>{order.PlayHours} 小时</Text>
                        <Space size={4}>
                          <Tag>
                            应收 {formatAmount(order.TheoreticalAmount)}
                          </Tag>
                          <Tag
                            color={
                              order.SettledAmount > 0 ? 'green' : 'default'
                            }
                          >
                            实收 {formatAmount(order.SettledAmount)}
                          </Tag>
                        </Space>
                        <Space.Compact block>
                          <Button
                            size="small"
                            block
                            disabled={!canSettle || isBusy}
                            onClick={() => onManualSettle(order)}
                          >
                            手动离场
                          </Button>
                          <Button
                            size="small"
                            block
                            type="primary"
                            disabled={!canSettle || isBusy}
                            loading={actioningId === order.ID}
                            onClick={() => onQuickSettle(order)}
                          >
                            快速离场
                          </Button>
                        </Space.Compact>
                      </Space>
                    </Card>
                  );
                })}
              </div>
            </div>
          );
        })}
      </Space>
    </section>
  );
};

const PlayOrderCard: React.FC<{
  order: API.PlayWorkbenchOrder;
  actioningId?: number;
  onManualSettle: (order: API.PlayWorkbenchOrder) => void;
  onQuickSettle: (order: API.PlayWorkbenchOrder) => void;
}> = ({ order, actioningId, onManualSettle, onQuickSettle }) => {
  const status = getOrderStatus(order);
  const isPending = status === 'pending';
  const isBusy = actioningId !== undefined;
  const meta = statusMeta[status];
  return (
    <Badge.Ribbon text={meta.label} color={meta.color}>
      <Card className={styles.orderCard}>
        <Space
          direction="vertical"
          size="middle"
          className={styles.cardContent}
        >
          <div>
            <Text type="secondary">实际结算金额</Text>
            <div className={styles.actualAmount}>
              {formatAmount(order.SettledAmount)}
            </div>
            {status !== 'settled' && (
              <Text type="secondary">
                当前理论金额 {formatAmount(order.TheoreticalAmount)}
              </Text>
            )}
          </div>
          <Descriptions column={1} size="small" colon={false}>
            <Descriptions.Item label="玩家 ID">
              {order.UserID || '—'}
            </Descriptions.Item>
            <Descriptions.Item label="昵称">
              {order.NickName || '未设置'}
            </Descriptions.Item>
            <Descriptions.Item label="手机号">
              {order.Phone || '未绑定'}
            </Descriptions.Item>
            <Descriptions.Item label="入场时间">
              {formatTime(order.InTime)}
            </Descriptions.Item>
            <Descriptions.Item label="离场时间">
              {formatTime(order.OutTime)}
            </Descriptions.Item>
            <Descriptions.Item label="计费时长">
              {order.PlayHours} 小时
            </Descriptions.Item>
          </Descriptions>
          {status === 'payment_pending' && (
            <Tag icon={<ClockCircleOutlined />} color="warning">
              玩家正在支付，请等待支付结果
            </Tag>
          )}
          <Space.Compact block className={styles.actions}>
            <Button
              block
              disabled={!isPending || isBusy}
              onClick={() => onManualSettle(order)}
            >
              手动离场
            </Button>
            <Button
              block
              type="primary"
              disabled={!isPending || isBusy}
              loading={actioningId === order.ID}
              onClick={() => onQuickSettle(order)}
            >
              快速离场
            </Button>
          </Space.Compact>
        </Space>
      </Card>
    </Badge.Ribbon>
  );
};

const PlayWorkbench: React.FC = () => {
  const [data, setData] = useState<API.PlayWorkbenchData>({
    Orders: [],
    RecentGroups: [],
    RefreshedAt: 0,
  });
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [manualOrder, setManualOrder] = useState<API.PlayWorkbenchOrder>();
  const [actioningId, setActioningId] = useState<number>();
  const requestIdRef = useRef(0);
  const [form] = Form.useForm<API.SettlePlayWorkbenchRequest>();

  const loadData = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    try {
      const response = await queryPlayWorkbench();
      if (requestId !== requestIdRef.current) {
        return;
      }
      if (response.Code === 0 && response.Data) {
        setData(response.Data);
      } else {
        message.error(response.Msg || response.Message || '获取游玩订单失败');
      }
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (!autoRefresh || manualOrder || actioningId !== undefined) {
      return;
    }
    const timer = window.setInterval(loadData, 10000);
    return () => window.clearInterval(timer);
  }, [actioningId, autoRefresh, loadData, manualOrder]);

  const openManualSettle = (order: API.PlayWorkbenchOrder) => {
    form.resetFields();
    setManualOrder(order);
  };

  const executeManualSettle = async () => {
    if (!manualOrder) {
      return;
    }
    const values = await form.validateFields();
    setActioningId(manualOrder.ID);
    try {
      const response = await settlePlayWorkbenchOrder(manualOrder.ID, values);
      if (response.Code !== 0) {
        message.error(response.Msg || response.Message || '手动离场失败');
        return;
      }
      message.success(response.Message || '手动离场成功');
      setManualOrder(undefined);
      form.resetFields();
      await loadData();
    } finally {
      setActioningId(undefined);
    }
  };

  const executeQuickSettle = async (order: API.PlayWorkbenchOrder) => {
    setActioningId(order.ID);
    try {
      const response = await quickSettlePlayWorkbenchOrder(order.ID);
      if (response.Code !== 0) {
        message.error(response.Msg || response.Message || '快速离场失败');
        return;
      }
      message.success(response.Message || '快速离场成功');
      await loadData();
    } finally {
      setActioningId(undefined);
    }
  };

  return (
    <Space direction="vertical" size="large" className={styles.page}>
      <Card>
        <Row gutter={[16, 16]} align="middle">
          <Col flex="auto">
            <Space wrap size="middle">
              <Space>
                <Text>自动刷新</Text>
                <Switch checked={autoRefresh} onChange={setAutoRefresh} />
              </Space>
              <Button
                size="large"
                icon={<ReloadOutlined />}
                loading={loading}
                onClick={loadData}
              >
                手动刷新
              </Button>
            </Space>
          </Col>
          <Col>
            <Statistic
              title="今日订单"
              value={data.Orders.length}
              suffix="单"
            />
          </Col>
          <Col>
            <Text type="secondary">
              更新于 {data.RefreshedAt ? formatTime(data.RefreshedAt) : '—'}
            </Text>
          </Col>
        </Row>
      </Card>

      <RecentSettlementGroups
        groups={data.RecentGroups || []}
        actioningId={actioningId}
        onManualSettle={openManualSettle}
        onQuickSettle={executeQuickSettle}
      />

      <Spin spinning={loading}>
        {(data.Orders || []).length === 0 ? (
          <Card>
            <Empty description="当前门店今日暂无游玩订单" />
          </Card>
        ) : (
          <Row gutter={[16, 16]}>
            {data.Orders.map((order) => (
              <Col xs={24} md={12} xl={8} xxl={6} key={order.ID}>
                <PlayOrderCard
                  order={order}
                  actioningId={actioningId}
                  onManualSettle={openManualSettle}
                  onQuickSettle={executeQuickSettle}
                />
              </Col>
            ))}
          </Row>
        )}
      </Spin>

      <Modal
        title={`手动离场 · ${
          manualOrder?.NickName || `订单 #${manualOrder?.ID}`
        }`}
        open={Boolean(manualOrder)}
        okText="确认结算"
        cancelText="取消"
        confirmLoading={actioningId === manualOrder?.ID}
        cancelButtonProps={{ disabled: actioningId !== undefined }}
        closable={actioningId === undefined}
        maskClosable={false}
        keyboard={actioningId === undefined}
        onOk={executeManualSettle}
        onCancel={() => setManualOrder(undefined)}
        destroyOnClose
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item
            name="Amount"
            label="实际结算金额（元）"
            rules={[
              { required: true, message: '请输入结算金额' },
              {
                type: 'number',
                min: 0,
                message: '结算金额不能小于 0',
              },
            ]}
          >
            <InputNumber
              min={0}
              precision={2}
              step={1}
              prefix="¥"
              style={{ width: '100%' }}
              placeholder="请输入实际结算金额"
            />
          </Form.Item>
          <Form.Item name="Comment" label="备注">
            <Input.TextArea
              maxLength={500}
              showCount
              rows={3}
              placeholder="选填，将与操作人一起写入审计描述"
            />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
};

export default PlayWorkbench;
