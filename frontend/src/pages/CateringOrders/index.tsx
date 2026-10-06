import { ProTable, Table } from '@/components/AdaptiveTable';
import { queryCateringOrderHistory } from '@/services/catering';
import type { ActionType, ProColumns } from '@ant-design/pro-components';
import { PageContainer } from '@ant-design/pro-components';
import { Descriptions, Space, Tag, Typography } from 'antd';
import { useRef } from 'react';

const { Paragraph, Text } = Typography;

const formatAmount = (amount?: number | null) =>
  amount === null || amount === undefined
    ? '—'
    : `¥${(amount / 100).toFixed(2)}`;

const cateringStatusMeta: Record<number, { text: string; color: string }> = {
  0: { text: '制作中', color: 'orange' },
  1: { text: '可取餐', color: 'green' },
  2: { text: '已完成', color: 'default' },
};

const payStatusMeta: Record<number, { text: string; color: string }> = {
  0: { text: '待支付', color: 'orange' },
  1: { text: '已支付', color: 'green' },
  2: { text: '已关闭', color: 'default' },
  3: { text: '已退款', color: 'red' },
};

const payTypeText: Record<number, string> = {
  0: '微信',
  1: '月卡',
  2: '线下',
  3: '储值钱包',
  4: '钱包 + 微信',
};

const PayStatusTag: React.FC<{ order: API.CateringOrder }> = ({ order }) => {
  if (!order.PayOrder) {
    return <Tag>无支付流水</Tag>;
  }
  const meta = payStatusMeta[order.PayOrder.PayStatus] || {
    text: `未知状态 ${order.PayOrder.PayStatus}`,
    color: 'default',
  };
  return <Tag color={meta.color}>{meta.text}</Tag>;
};

const OrderDetails: React.FC<{ order: API.CateringOrder }> = ({ order }) => (
  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
    <Descriptions bordered size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
      <Descriptions.Item label="订单 ID">{order.Id}</Descriptions.Item>
      <Descriptions.Item label="OpenID">
        <Text copyable>{order.OpenId}</Text>
      </Descriptions.Item>
      <Descriptions.Item label="取餐方式">
        {order.Takeaway ? '外带' : '堂食'}
      </Descriptions.Item>
      <Descriptions.Item label="桌台">
        {order.TableInfo?.Name || '—'}
      </Descriptions.Item>
      <Descriptions.Item label="订单金额">
        {formatAmount(order.TotalPrice)}
      </Descriptions.Item>
      <Descriptions.Item label="支付状态">
        <PayStatusTag order={order} />
      </Descriptions.Item>
      <Descriptions.Item label="支付方式">
        {order.PayOrder
          ? payTypeText[order.PayOrder.PayType] ||
            `类型 ${order.PayOrder.PayType}`
          : '—'}
      </Descriptions.Item>
      <Descriptions.Item label="支付金额">
        {formatAmount(order.PayOrder?.Amount)}
      </Descriptions.Item>
      <Descriptions.Item label="支付完成时间">
        {order.PayOrder?.PayEndTime || '—'}
      </Descriptions.Item>
      <Descriptions.Item label="商户订单号" span={2}>
        {order.PayOrder?.OrderId ? (
          <Text copyable>{order.PayOrder.OrderId}</Text>
        ) : (
          '—'
        )}
      </Descriptions.Item>
      <Descriptions.Item label="支付描述">
        {order.PayOrder?.Description || '—'}
      </Descriptions.Item>
      <Descriptions.Item label="订单备注" span={3}>
        {order.Comment || '—'}
      </Descriptions.Item>
      <Descriptions.Item label="创建时间">{order.CreatedAt}</Descriptions.Item>
      <Descriptions.Item label="更新时间">
        {order.UpdatedAt || '—'}
      </Descriptions.Item>
    </Descriptions>

    <Table<API.CateringOrderItem>
      rowKey="Id"
      size="small"
      pagination={false}
      dataSource={order.Items || []}
      columns={[
        { title: '餐品', dataIndex: 'DishName' },
        {
          title: '规格',
          dataIndex: 'SelectionsText',
          render: (value) => value || '—',
        },
        { title: '数量', dataIndex: 'Count', width: 100 },
        {
          title: '小计',
          dataIndex: 'TotalPrice',
          width: 120,
          render: (value) => formatAmount(value),
        },
      ]}
    />
  </Space>
);

const CateringOrdersPage: React.FC = () => {
  const actionRef = useRef<ActionType>();

  const columns: ProColumns<API.CateringOrder>[] = [
    {
      title: '关键字',
      dataIndex: 'Keyword',
      hideInTable: true,
      fieldProps: {
        placeholder: '订单 ID / 取餐号 / 昵称 / OpenID',
      },
    },
    {
      title: '订单 ID',
      dataIndex: 'Id',
      width: 90,
      search: false,
    },
    {
      title: '取餐号',
      dataIndex: 'Code',
      width: 100,
      search: false,
    },
    {
      title: '用户昵称',
      dataIndex: ['User', 'NickName'],
      width: 120,
      search: false,
      render: (_, order) => order.User?.NickName || '—',
    },
    {
      title: '手机号',
      dataIndex: ['User', 'Phone'],
      width: 130,
      search: false,
      render: (_, order) => order.User?.Phone || '—',
    },
    {
      title: '订单金额',
      dataIndex: 'TotalPrice',
      width: 110,
      search: false,
      render: (_, order) => formatAmount(order.TotalPrice),
    },
    {
      title: '制作状态',
      dataIndex: 'Status',
      width: 110,
      valueEnum: {
        0: { text: '制作中', status: 'Processing' },
        1: { text: '可取餐', status: 'Success' },
        2: { text: '已完成', status: 'Default' },
      },
      render: (_, order) => {
        const meta = cateringStatusMeta[order.Status] || {
          text: `未知状态 ${order.Status}`,
          color: 'default',
        };
        return <Tag color={meta.color}>{meta.text}</Tag>;
      },
    },
    {
      title: '支付状态',
      dataIndex: 'PayStatus',
      width: 110,
      valueEnum: {
        0: { text: '待支付', status: 'Processing' },
        1: { text: '已支付', status: 'Success' },
        2: { text: '已关闭', status: 'Default' },
        3: { text: '已退款', status: 'Error' },
        none: { text: '无支付流水', status: 'Default' },
      },
      render: (_, order) => <PayStatusTag order={order} />,
    },
    {
      title: '取餐方式',
      dataIndex: 'Takeaway',
      width: 100,
      search: false,
      render: (_, order) => (
        <Tag color={order.Takeaway ? 'blue' : 'default'}>
          {order.Takeaway ? '外带' : '堂食'}
        </Tag>
      ),
    },
    {
      title: '下单时间',
      dataIndex: 'CreatedAt',
      width: 170,
      valueType: 'dateTime',
      hideInSearch: true,
    },
    {
      title: '下单时间',
      dataIndex: 'CreatedTimeRange',
      valueType: 'dateTimeRange',
      hideInTable: true,
      search: {
        transform: (value: string[]) => ({
          StartTime: value?.[0],
          EndTime: value?.[1],
        }),
      },
    },
    {
      title: '支付时间',
      dataIndex: ['PayOrder', 'PayEndTime'],
      width: 170,
      search: false,
      render: (_, order) => order.PayOrder?.PayEndTime || '—',
    },
  ];

  return (
    <PageContainer title="历史餐饮订单">
      <Paragraph type="secondary">
        本页面展示当前门店全部餐饮订单，仅供查阅，不提供制作、取餐或结算操作。
      </Paragraph>
      <ProTable<API.CateringOrder>
        actionRef={actionRef}
        headerTitle="餐饮订单记录"
        rowKey="Id"
        columns={columns}
        scroll={{ x: 1350 }}
        toolbar={{
          actions: [],
        }}
        expandable={{
          expandedRowRender: (order) => <OrderDetails order={order} />,
          rowExpandable: () => true,
        }}
        search={{
          labelWidth: 100,
          defaultCollapsed: false,
        }}
        request={async (params) => {
          const response = await queryCateringOrderHistory({
            current: params.current,
            pageSize: params.pageSize,
            Keyword: params.Keyword,
            Status: params.Status as 0 | 1 | 2 | undefined,
            PayStatus: params.PayStatus as 0 | 1 | 2 | 3 | 'none' | undefined,
            StartTime: params.StartTime,
            EndTime: params.EndTime,
          });
          return {
            data: response.Data?.Items || [],
            total: response.Data?.Total || 0,
            success: response.Code === 0,
          };
        }}
        pagination={{
          showQuickJumper: true,
          showSizeChanger: true,
          defaultPageSize: 20,
          pageSizeOptions: ['20', '50', '100'],
        }}
      />
    </PageContainer>
  );
};

export default CateringOrdersPage;
