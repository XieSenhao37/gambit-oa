import { ProTable } from '@/components/AdaptiveTable';
import { queryPointWithdraws } from '@/services/point';
import {
  PageContainer,
  type ActionType,
  type ProColumns,
} from '@ant-design/pro-components';
import { Tag } from 'antd';
import { useRef } from 'react';

const STATUS_VALUE_ENUM = {
  0: { text: '待发放', status: 'Processing' },
  1: { text: '已发放', status: 'Success' },
  2: { text: '已过期', status: 'Default' },
  3: { text: '已取消', status: 'Error' },
};

const STATUS_COLOR: Record<number, string> = {
  0: 'blue',
  1: 'green',
  2: 'default',
  3: 'red',
};

const PointWithdrawsPage: React.FC = () => {
  const actionRef = useRef<ActionType>();

  const columns: ProColumns<API.PointWithdrawItem>[] = [
    { title: 'ID', dataIndex: 'Id', width: 70, search: false },
    {
      title: '申请用户',
      dataIndex: 'OpenID',
      width: 220,
      fieldProps: { placeholder: '搜索用户 OpenID' },
      render: (_, record) => (
        <div>
          <div>{record.UserNickName || '未知用户'}</div>
          <div style={{ color: '#999', fontSize: 12 }}>{record.OpenID}</div>
        </div>
      ),
    },
    {
      title: '提取积分',
      dataIndex: 'Points',
      width: 110,
      search: false,
      render: (_, record) => <Tag color="blue">{record.Points} 积分</Tag>,
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
      title: '发放员工',
      dataIndex: 'IssuerOpenID',
      width: 200,
      search: false,
      render: (_, record) =>
        record.IssuerOpenID ? (
          <div>
            <div>{record.IssuerNickName || '员工'}</div>
            <div style={{ color: '#999', fontSize: 12 }}>
              {record.IssuerOpenID}
            </div>
          </div>
        ) : (
          <span style={{ color: '#bbb' }}>—</span>
        ),
    },
    { title: '发放时间', dataIndex: 'IssuedAt', width: 170, search: false },
    { title: '过期时间', dataIndex: 'ExpireAt', width: 170, search: false },
    { title: '申请时间', dataIndex: 'CreatedAt', width: 170, search: false },
  ];

  return (
    <PageContainer>
      <ProTable<API.PointWithdrawItem>
        headerTitle="积分提取审计"
        actionRef={actionRef}
        rowKey="Id"
        scroll={{ x: 1100 }}
        search={{ labelWidth: 'auto', defaultCollapsed: false }}
        request={async (params) => {
          const response = await queryPointWithdraws({
            current: params.current,
            pageSize: params.pageSize,
            Keyword: params.OpenID,
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

export default PointWithdrawsPage;
