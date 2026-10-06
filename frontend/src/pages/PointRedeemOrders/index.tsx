import { ProTable } from '@/components/AdaptiveTable';
import { queryPointRedeemOrders } from '@/services/point';
import {
  PageContainer,
  type ActionType,
  type ProColumns,
} from '@ant-design/pro-components';
import { Image, Tag } from 'antd';
import { useRef } from 'react';

const STATUS_VALUE_ENUM = {
  0: { text: '待领取', status: 'Processing' },
  1: { text: '已完成', status: 'Success' },
  2: { text: '已取消', status: 'Default' },
};

const STATUS_COLOR: Record<number, string> = {
  0: 'blue',
  1: 'green',
  2: 'default',
};

const PointRedeemOrdersPage: React.FC = () => {
  const actionRef = useRef<ActionType>();

  const columns: ProColumns<API.PointRedeemOrderItem>[] = [
    { title: 'ID', dataIndex: 'Id', width: 70, search: false },
    {
      title: '订单号/用户',
      dataIndex: 'Keyword',
      width: 240,
      fieldProps: { placeholder: '搜索订单号/用户/商品' },
      render: (_, record) => (
        <div>
          <div>{record.OrderNo}</div>
          <div style={{ color: '#999', fontSize: 12 }}>
            {record.UserNickName || '未知用户'} · {record.OpenID}
          </div>
        </div>
      ),
    },
    {
      title: '兑换商品',
      dataIndex: 'ProductName',
      width: 260,
      search: false,
      render: (_, record) => (
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          {record.ProductImageUrl ? (
            <Image
              width={56}
              height={56}
              src={record.ProductImageUrl}
              style={{ objectFit: 'cover', borderRadius: 8 }}
            />
          ) : null}
          <div>
            <div>{record.ProductName}</div>
            <div style={{ color: '#999', fontSize: 12 }}>
              商品 ID：{record.ProductId}
            </div>
          </div>
        </div>
      ),
    },
    {
      title: '数量',
      dataIndex: 'Quantity',
      width: 90,
      search: false,
      render: (_, record) => `x${record.Quantity}`,
    },
    {
      title: '消耗积分',
      dataIndex: 'TotalPoints',
      width: 120,
      search: false,
      render: (_, record) => <Tag color="blue">{record.TotalPoints} 积分</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'Status',
      width: 120,
      valueType: 'select',
      valueEnum: STATUS_VALUE_ENUM,
      render: (_, record) => (
        <Tag color={STATUS_COLOR[record.Status] || 'default'}>
          {record.StatusText}
        </Tag>
      ),
    },
    {
      title: '核销员工',
      dataIndex: 'VerifierOpenID',
      width: 220,
      search: false,
      render: (_, record) =>
        record.VerifierOpenID ? (
          <div>
            <div>{record.VerifierNickName || '员工'}</div>
            <div style={{ color: '#999', fontSize: 12 }}>
              {record.VerifierOpenID}
            </div>
          </div>
        ) : (
          <span style={{ color: '#bbb' }}>—</span>
        ),
    },
    { title: '兑换时间', dataIndex: 'CreatedAt', width: 170, search: false },
    { title: '核销时间', dataIndex: 'VerifiedAt', width: 170, search: false },
  ];

  return (
    <PageContainer>
      <ProTable<API.PointRedeemOrderItem>
        headerTitle="积分兑换明细"
        actionRef={actionRef}
        rowKey="Id"
        scroll={{ x: 1400 }}
        search={{ labelWidth: 'auto', defaultCollapsed: false }}
        request={async (params) => {
          const response = await queryPointRedeemOrders({
            current: params.current,
            pageSize: params.pageSize,
            Keyword: params.Keyword,
            Status: params.Status,
          });
          if (response.Code === 0 && response.Data) {
            return {
              data: response.Data.Items || [],
              total: response.Data.Total || 0,
              success: true,
            };
          }
          return { data: [], total: 0, success: false };
        }}
        columns={columns}
        pagination={{
          showQuickJumper: true,
          showSizeChanger: true,
          defaultPageSize: 20,
          pageSizeOptions: ['10', '20', '50', '100'],
        }}
      />
    </PageContainer>
  );
};

export default PointRedeemOrdersPage;
