import { ProTable } from '@/components/AdaptiveTable';
import { queryUsers } from '@/services/users';
import type { ActionType, ProColumns } from '@ant-design/pro-components';
import { PageContainer } from '@ant-design/pro-components';
import { Alert, Button } from 'antd';
import { useRef, useState } from 'react';

const ROLE_VALUE_ENUM = {
  0: { text: '普通用户' },
  1: { text: '店员' },
  2: { text: '兼职' },
  125: { text: '店长' },
  126: { text: '管理员' },
  127: { text: '超级管理员' },
};

const USER_METRIC_SORT_FIELDS = [
  'PointBalance',
  'WalletBalance',
  'TotalConsumptionAmount',
] as const;

const formatCents = (value?: number) =>
  value === null || value === undefined ? '-' : `¥${(value / 100).toFixed(2)}`;

const UserList: React.FC = () => {
  const actionRef = useRef<ActionType>();
  const [listError, setListError] = useState<string>();
  const columns: ProColumns<API.UserInfo>[] = [
    {
      title: '用户ID',
      dataIndex: 'Id',
      width: 80,
    },
    {
      title: 'OpenID',
      dataIndex: 'OpenId',
      width: 200,
      ellipsis: true,
    },
    {
      title: '用户类型',
      dataIndex: 'UserType',
      width: 100,
      valueEnum: {
        0: { text: '小程序用户' },
      },
      search: false,
    },
    {
      title: '角色',
      dataIndex: 'Role',
      width: 100,
      valueEnum: ROLE_VALUE_ENUM,
    },
    {
      title: '昵称',
      dataIndex: 'NickName',
      width: 120,
    },
    {
      title: '手机号',
      dataIndex: 'PhoneNumber',
      width: 120,
    },
    {
      title: '月卡到期',
      dataIndex: 'MonthCardExpire',
      width: 150,
      search: false,
    },
    {
      title: '积分余额',
      dataIndex: 'PointBalance',
      width: 110,
      search: false,
      sorter: true,
      render: (value) => value ?? 0,
    },
    {
      title: '储值余额',
      dataIndex: 'WalletBalance',
      width: 120,
      search: false,
      sorter: true,
      render: (_, row) => formatCents(row.WalletBalance),
    },
    {
      title: '累计消费金额',
      dataIndex: 'TotalConsumptionAmount',
      width: 140,
      search: false,
      sorter: true,
      render: (_, row) => formatCents(row.TotalConsumptionAmount),
    },
    {
      title: '是否月卡用户',
      dataIndex: 'IsMonthCardUser',
      hideInTable: true,
      valueType: 'select',
      valueEnum: {
        '1': { text: '月卡用户', status: 'Success' },
        '0': { text: '非月卡用户', status: 'Default' },
      },
    },
    {
      title: '创建时间',
      dataIndex: 'CreatedAt',
      width: 150,
      search: false,
    },
  ];

  return (
    <>
      <PageContainer>
        {listError && (
          <Alert
            type="error"
            showIcon
            message="用户列表加载失败，并非没有用户"
            description={listError}
            action={
              <Button onClick={() => actionRef.current?.reload()}>重试</Button>
            }
            style={{ marginBottom: 16 }}
          />
        )}
        <ProTable<API.UserInfo>
          headerTitle="用户列表"
          actionRef={actionRef}
          rowKey="Id"
          search={{
            labelWidth: 120,
          }}
          request={async (params, sort) => {
            setListError(undefined);
            try {
              const sortField = USER_METRIC_SORT_FIELDS.find(
                (field) => sort?.[field],
              );
              const sortOrder = sortField ? sort?.[sortField] : undefined;
              const response = await queryUsers({
                Current: params.current,
                PageSize: params.pageSize,
                Id: params.Id,
                OpenId: params.OpenId,
                Role: params.Role,
                UserType: params.UserType,
                NickName: params.NickName,
                PhoneNumber: params.PhoneNumber,
                IsMonthCardUser: params.IsMonthCardUser,
                SortField: sortField,
                SortOrder:
                  sortOrder === 'ascend'
                    ? 'asc'
                    : sortOrder === 'descend'
                    ? 'desc'
                    : undefined,
              });

              if (response.Code === 0) {
                return {
                  data: response.Data?.Items || [],
                  total: response.Data?.Total || 0,
                  success: true,
                };
              }
              setListError('请求未成功，请重试并核对服务端日志。');
              return { data: [], total: 0, success: false };
            } catch (error: any) {
              const errorId = error?.response?.data?.ErrorId;
              setListError(
                errorId
                  ? `错误编号：${errorId}。请提供此编号对应的服务端日志。`
                  : '请求未成功，请重试并核对服务端日志。',
              );
              return { data: [], total: 0, success: false };
            }
          }}
          columns={columns}
          scroll={{ x: 1600 }}
          pagination={{
            showQuickJumper: true,
            showSizeChanger: true,
            defaultPageSize: 10,
            pageSizeOptions: ['10', '20', '50', '100'],
          }}
        />
      </PageContainer>
    </>
  );
};

export default UserList;
