import { ProTable } from '@/components/AdaptiveTable';
import { queryOrders } from '@/services/orders';
import type { ProColumns } from '@ant-design/pro-components';
import { PageContainer } from '@ant-design/pro-components';
import { Typography } from 'antd';

const OrderList: React.FC = () => {
  const columns: ProColumns<API.PlayOrder>[] = [
    {
      title: '订单ID',
      dataIndex: 'Id',
      width: 80,
    },
    {
      title: '用户ID',
      dataIndex: ['User', 'Id'],
      width: 80,
      valueType: 'digit',
      hideInTable: false,
    },
    {
      title: '用户昵称',
      dataIndex: ['User', 'NickName'],
      width: 120,
      search: false,
    },
    {
      title: 'OpenID',
      dataIndex: 'OpenId',
      width: 220,
      copyable: true,
      ellipsis: true,
    },
    {
      title: '用户手机号',
      dataIndex: ['User', 'Phone'],
      width: 120,
      search: false,
    },
    {
      title: '入场时间',
      dataIndex: 'InTime',
      width: 150,
      valueType: 'dateTime',
      hideInSearch: true,
    },
    {
      title: '入场时间',
      dataIndex: 'InTime',
      valueType: 'dateTimeRange',
      hideInTable: true,
      search: {
        transform: (value: any) => {
          return {
            InTimeStart: value?.[0],
            InTimeEnd: value?.[1],
          };
        },
      },
    },
    {
      title: '出场时间',
      dataIndex: 'OutTime',
      width: 150,
      valueType: 'dateTime',
      hideInSearch: true,
    },
    {
      title: '出场时间',
      dataIndex: 'OutTime',
      valueType: 'dateTimeRange',
      hideInTable: true,
      search: {
        transform: (value: any) => {
          return {
            OutTimeStart: value?.[0],
            OutTimeEnd: value?.[1],
          };
        },
      },
    },
    {
      title: '游玩时长(小时)',
      dataIndex: 'PlayTime',
      width: 100,
      search: false,
    },
    {
      title: '单价(元/小时)',
      dataIndex: 'UnitPrice',
      width: 100,
      render: (_, record) =>
        record.UnitPrice ? (record.UnitPrice / 100).toFixed(2) : '-',
      search: false,
    },
    {
      title: '金额(元)',
      dataIndex: 'Amount',
      width: 100,
      render: (_, record) =>
        record.Amount ? (record.Amount / 100).toFixed(2) : '-',
      search: false,
    },
    {
      title: '结算状态',
      dataIndex: 'SettleStatus',
      width: 100,
      valueEnum: {
        0: { text: '待结算', status: 'warning' },
        1: { text: '已结算', status: 'success' },
      },
    },
    {
      title: '备注',
      dataIndex: 'Comment',
      ellipsis: true,
      search: false,
    },
    {
      title: '创建时间',
      dataIndex: 'CreatedAt',
      width: 150,
      search: false,
    },
    {
      title: '更新时间',
      dataIndex: 'UpdatedAt',
      width: 150,
      valueType: 'dateTime',
      search: false,
    },
  ];

  return (
    <PageContainer title="历史游玩订单">
      <Typography.Paragraph type="secondary">
        本页面仅用于查阅历史订单，离场与结算请前往工作台操作。
      </Typography.Paragraph>
      <ProTable<API.PlayOrder>
        headerTitle="游玩订单记录"
        rowKey="Id"
        scroll={{ x: 1500 }}
        search={{
          labelWidth: 120,
          defaultCollapsed: false,
        }}
        request={async (params) => {
          const response = await queryOrders({
            current: params.current,
            pageSize: params.pageSize,
            UserId: params.User?.Id
              ? parseInt(params.User.Id.toString())
              : undefined,
            OpenId: params.OpenId,
            SettleStatus: params.SettleStatus as 0 | 1,
            InTimeStart: params.InTimeStart,
            InTimeEnd: params.InTimeEnd,
            OutTimeStart: params.OutTimeStart,
            OutTimeEnd: params.OutTimeEnd,
          });
          return {
            data: response.Data?.Items || [],
            total: response.Data?.Total || 0,
            success: response.Code === 0,
          };
        }}
        columns={columns}
        pagination={{
          showQuickJumper: true,
          showSizeChanger: true,
          defaultPageSize: 10,
          pageSizeOptions: ['10', '20', '50', '100'],
        }}
      />
    </PageContainer>
  );
};

export default OrderList;
