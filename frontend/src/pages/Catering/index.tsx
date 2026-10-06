import {
  completeCateringOrder,
  finishCateringOrder,
  queryCateringOrders,
} from '@/services/catering';
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { PageContainer } from '@ant-design/pro-components';
import {
  Badge,
  Button,
  Card,
  Col,
  Empty,
  Input,
  List,
  message,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Switch,
  Tag,
  Typography,
} from 'antd';
import { useCallback, useEffect, useState } from 'react';

const { Text, Title } = Typography;

const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '制作中', value: 0 },
  { label: '可取餐', value: 1 },
  { label: '已完成', value: 2 },
];

const statusMeta = {
  0: {
    text: '制作中',
    color: 'orange',
    actionText: '制作完成并通知顾客',
  },
  1: {
    text: '可取餐',
    color: 'green',
    actionText: '顾客已取餐，完成订单',
  },
  2: {
    text: '已完成',
    color: 'default',
    actionText: '',
  },
} as const;

const getWaitingColor = (minutes: number) => {
  if (minutes >= 15) {
    return 'red';
  }
  if (minutes >= 8) {
    return 'orange';
  }
  return 'blue';
};

const formatPrice = (price?: number) => {
  if (!price) {
    return '0.00';
  }
  return (price / 100).toFixed(2);
};

const getSelectionTags = (selectionsText?: string) => {
  if (!selectionsText) {
    return [];
  }
  return selectionsText
    .split(/[，,|]/)
    .map((item) => item.trim())
    .filter(Boolean);
};

const getStatusTimeTag = (order: API.CateringOrder) => {
  if (order.Status === 0) {
    return {
      color: getWaitingColor(order.WaitingMinutes),
      minutes: order.WaitingMinutes,
      text: `等待 ${order.WaitingMinutes} 分钟`,
    };
  }
  if (order.Status === 1) {
    const readyMinutes = order.ReadyMinutes || 0;
    return {
      color: getWaitingColor(readyMinutes),
      minutes: readyMinutes,
      text: `等待 ${readyMinutes} 分钟`,
    };
  }
  return {
    color: 'default',
    minutes: 0,
    text: '已完成',
  };
};

export const CateringWorkbench: React.FC = () => {
  const [orders, setOrders] = useState<API.CateringOrder[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [finishingId, setFinishingId] = useState<number>();
  const [completingId, setCompletingId] = useState<number>();
  const [status, setStatus] = useState<'all' | 0 | 1 | 2>('all');
  const [keyword, setKeyword] = useState('');
  const [onlyToday, setOnlyToday] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const response = await queryCateringOrders({
        current: 1,
        pageSize: 80,
        Status: status === 'all' ? undefined : status,
        Keyword: keyword || undefined,
        OnlyToday: onlyToday ? '1' : '0',
      });

      if (response.Code === 0) {
        setOrders(response.Data?.Items || []);
        setTotal(response.Data?.Total || 0);
      } else {
        message.error(response.Msg || response.Message || '获取餐饮订单失败');
      }
    } finally {
      setLoading(false);
    }
  }, [keyword, onlyToday, status]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (!autoRefresh) {
      return;
    }
    const timer = window.setInterval(loadData, 10000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, loadData]);

  const executeFinish = async (order: API.CateringOrder) => {
    setFinishingId(order.Id);
    try {
      const response = await finishCateringOrder(order.Id);
      if (response.Code === 0) {
        if (response.Data?.NotifyError) {
          message.warning(
            `已设为可取餐，但订阅消息发送失败：${response.Data.NotifyError}`,
          );
        } else if (response.Data?.NotifySent) {
          message.success(response.Message || '已标记制作完成，并已通知顾客');
        } else {
          message.success(response.Message || '已标记制作完成');
        }
        await loadData();
      } else {
        message.error(response.Msg || response.Message || '操作失败');
      }
    } finally {
      setFinishingId(undefined);
    }
  };

  const executeComplete = async (order: API.CateringOrder) => {
    setCompletingId(order.Id);
    try {
      const response = await completeCateringOrder(order.Id);
      if (response.Code === 0) {
        message.success(response.Message || '订单已完成');
        await loadData();
      } else {
        message.error(response.Msg || response.Message || '操作失败');
      }
    } finally {
      setCompletingId(undefined);
    }
  };

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card>
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} sm={8} md={6}>
            <Statistic
              title={status === 'all' ? '全部状态' : statusMeta[status].text}
              value={total}
              suffix="单"
            />
          </Col>
          <Col xs={24} sm={16} md={18}>
            <Space wrap size="middle">
              <Select
                value={status}
                options={statusOptions}
                onChange={setStatus}
                style={{ width: 140 }}
                size="large"
              />
              <Input.Search
                allowClear
                placeholder="搜索取餐号 / 昵称 / OpenID"
                onSearch={setKeyword}
                style={{ width: 280 }}
                size="large"
              />
              <Space>
                <Text>只看今日</Text>
                <Switch checked={onlyToday} onChange={setOnlyToday} />
              </Space>
              <Space>
                <Text>自动刷新</Text>
                <Switch checked={autoRefresh} onChange={setAutoRefresh} />
              </Space>
              <Button size="large" icon={<ReloadOutlined />} onClick={loadData}>
                手动刷新
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Spin spinning={loading}>
        {orders.length === 0 ? (
          <Card>
            <Empty
              description={
                status === 'all'
                  ? '暂无餐饮订单'
                  : `暂无${statusMeta[status].text}订单`
              }
            />
          </Card>
        ) : (
          <Row gutter={[16, 16]}>
            {orders.map((order) => {
              const statusTimeTag = getStatusTimeTag(order);
              return (
                <Col xs={24} lg={12} xl={8} key={order.Id}>
                  <Badge.Ribbon
                    text={statusMeta[order.Status].text}
                    color={statusMeta[order.Status].color}
                  >
                    <Card
                      style={{
                        borderColor:
                          order.Status !== 2 && statusTimeTag.minutes >= 15
                            ? '#ff4d4f'
                            : undefined,
                        minHeight: 460,
                      }}
                    >
                      <Space
                        direction="vertical"
                        size="middle"
                        style={{ width: '100%' }}
                      >
                        <Row justify="space-between" align="middle">
                          <Col>
                            <Text type="secondary">取餐号</Text>
                            <Title level={2} style={{ margin: 0 }}>
                              {order.Code}
                            </Title>
                          </Col>
                          <Col>
                            <Tag
                              icon={<ClockCircleOutlined />}
                              color={statusTimeTag.color}
                              style={{ fontSize: 16, padding: '6px 10px' }}
                            >
                              {statusTimeTag.text}
                            </Tag>
                          </Col>
                        </Row>

                        <Space wrap>
                          <Tag color="blue">
                            实付 ¥{formatPrice(order.TotalPrice)}
                          </Tag>
                          {order.User?.NickName && (
                            <Tag>{order.User.NickName}</Tag>
                          )}
                          {order.User?.Phone && <Tag>{order.User.Phone}</Tag>}
                        </Space>

                        <List
                          dataSource={order.Items}
                          split={false}
                          renderItem={(item) => (
                            <List.Item style={{ padding: '6px 0' }}>
                              <Space
                                direction="vertical"
                                size={0}
                                style={{ width: '100%' }}
                              >
                                <Row justify="space-between">
                                  <Col>
                                    <Text strong style={{ fontSize: 16 }}>
                                      {item.DishName}
                                    </Text>
                                  </Col>
                                  <Col>
                                    <Text strong>x{item.Count}</Text>
                                  </Col>
                                </Row>
                                {getSelectionTags(item.SelectionsText).length >
                                  0 && (
                                  <Space
                                    wrap
                                    size={[4, 4]}
                                    style={{ marginTop: 4 }}
                                  >
                                    {getSelectionTags(item.SelectionsText).map(
                                      (selection) => (
                                        <Tag key={selection} color="gold">
                                          {selection}
                                        </Tag>
                                      ),
                                    )}
                                  </Space>
                                )}
                              </Space>
                            </List.Item>
                          )}
                        />

                        {order.Comment && (
                          <Card size="small" style={{ background: '#fffbe6' }}>
                            <Text strong>备注：</Text>
                            <Text>{order.Comment}</Text>
                          </Card>
                        )}

                        {order.Status === 0 && (
                          <Button
                            block
                            type="primary"
                            size="large"
                            icon={<CheckCircleOutlined />}
                            loading={finishingId === order.Id}
                            onClick={() => executeFinish(order)}
                            style={{
                              height: 64,
                              fontSize: 20,
                              fontWeight: 600,
                            }}
                          >
                            {statusMeta[0].actionText}
                          </Button>
                        )}

                        {order.Status === 1 && (
                          <Button
                            block
                            type="primary"
                            size="large"
                            icon={<CheckCircleOutlined />}
                            loading={completingId === order.Id}
                            onClick={() => executeComplete(order)}
                            style={{
                              height: 64,
                              fontSize: 20,
                              fontWeight: 600,
                              background: '#389e0d',
                              borderColor: '#389e0d',
                            }}
                          >
                            {statusMeta[1].actionText}
                          </Button>
                        )}

                        {order.Status === 2 && (
                          <Button
                            block
                            disabled
                            size="large"
                            style={{ height: 64, fontSize: 18 }}
                          >
                            已完成
                          </Button>
                        )}
                      </Space>
                    </Card>
                  </Badge.Ribbon>
                </Col>
              );
            })}
          </Row>
        )}
      </Spin>
    </Space>
  );
};

const CateringPage: React.FC = () => (
  <PageContainer>
    <CateringWorkbench />
  </PageContainer>
);

export default CateringPage;
