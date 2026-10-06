import { ProTable } from '@/components/AdaptiveTable';
import {
  approveRefundRequest,
  queryRefundRequests,
  rejectRefundRequest,
} from '@/services/refund';
import type { ActionType, ProColumns } from '@ant-design/pro-components';
import { PageContainer } from '@ant-design/pro-components';
import { Button, Input, message, Modal, Space, Tag, Typography } from 'antd';
import dayjs from 'dayjs';
import { useEffect, useRef, useState } from 'react';
import './index.less';

const { Text } = Typography;

const statusMeta: Record<
  API.RefundRequestStatus,
  { text: string; color: string }
> = {
  pending_review: { text: '待审核', color: 'blue' },
  approved: { text: '已通过', color: 'geekblue' },
  rejected: { text: '已拒绝', color: 'red' },
  refunding: { text: '退款中', color: 'orange' },
  refunded: { text: '已退款', color: 'green' },
  refund_failed: { text: '退款失败', color: 'volcano' },
};

const orderTypeMeta = {
  play: { text: '玩乐', color: 'purple' },
  catering: { text: '吃喝', color: 'cyan' },
  organization: { text: '组局意向金', color: 'blue' },
} satisfies Record<API.RefundOrderType, { text: string; color: string }>;

const formatPrice = (value?: number) => `¥${((value || 0) / 100).toFixed(2)}`;

const formatTime = (value?: string) =>
  value && dayjs(value).isValid()
    ? dayjs(value).format('YYYY-MM-DD HH:mm')
    : value || '—';

const getOrderTitle = (record: API.RefundRequest) =>
  record.OrderSnapshot?.ActivityTitle ||
  record.OrderSnapshot?.Title ||
  `订单 ${record.OrderId}`;

const getOrderTypeMeta = (record: API.RefundRequest) =>
  orderTypeMeta[record.OrderType] || {
    text: record.OrderSnapshot?.TypeText || '未知类型',
    color: 'default',
  };

const getStatusMeta = (record: API.RefundRequest) => {
  if (record.OrderType === 'organization') {
    if (record.Status === 'pending_review') {
      return record.OrderSnapshot?.RegistrationStatus === 2
        ? { text: '已取消 / 待处理', color: 'gold' }
        : { text: '待到店退款', color: 'blue' };
    }
    if (record.Status === 'rejected') {
      return { text: '不退款', color: 'default' };
    }
  }
  return statusMeta[record.Status] || { text: record.Status, color: 'default' };
};

const canBatchRefund = (record: API.RefundRequest) =>
  record.OrderType === 'organization' &&
  record.Status === 'pending_review' &&
  record.OrderSnapshot?.RegistrationStatus === 1;

const RefundsPage: React.FC = () => {
  const actionRef = useRef<ActionType>();
  const [approvingId, setApprovingId] = useState<number>();
  const [rejectingId, setRejectingId] = useState<number>();
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [selectedRows, setSelectedRows] = useState<API.RefundRequest[]>([]);
  const [batchApproving, setBatchApproving] = useState(false);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!batchApproving) {
        actionRef.current?.reload();
      }
    }, 10000);
    return () => window.clearInterval(timer);
  }, [batchApproving]);

  const handleBatchApprove = () => {
    const records = selectedRows.filter(canBatchRefund);
    const totalAmount = records.reduce((sum, record) => sum + record.Amount, 0);
    Modal.confirm({
      title: `批量退款 ${records.length} 人？`,
      content: (
        <Space direction="vertical" size={4}>
          <Text>退款总额：{formatPrice(totalAmount)}</Text>
          <Text type="secondary">
            仅处理已报名、待到店退款的组局意向金。确认后将逐笔调用微信原路退款。
          </Text>
        </Space>
      ),
      okText: '确认退款',
      cancelText: '取消',
      onOk: async () => {
        setBatchApproving(true);
        let nextIndex = 0;
        let successCount = 0;
        const failures: string[] = [];
        const runWorker = async () => {
          while (nextIndex < records.length) {
            const record = records[nextIndex];
            nextIndex += 1;
            try {
              const response = await approveRefundRequest(record.Id);
              if (response.Code === 0) {
                successCount += 1;
              } else {
                failures.push(
                  `${record.User?.NickName || `申请 ${record.Id}`}：${
                    response.Msg || response.Message || '操作失败'
                  }`,
                );
              }
            } catch {
              failures.push(
                `${record.User?.NickName || `申请 ${record.Id}`}：请求失败`,
              );
            }
          }
        };
        try {
          await Promise.all(
            Array.from({ length: Math.min(3, records.length) }, () =>
              runWorker(),
            ),
          );
          if (failures.length === 0) {
            message.success(`已发起 ${successCount} 笔退款`);
          } else {
            Modal.warning({
              title: `完成 ${successCount} 笔，失败 ${failures.length} 笔`,
              content: (
                <Space direction="vertical" size={2}>
                  {failures.map((failure) => (
                    <Text key={failure}>{failure}</Text>
                  ))}
                </Space>
              ),
            });
          }
          setSelectedRowKeys([]);
          setSelectedRows([]);
          actionRef.current?.reload();
        } finally {
          setBatchApproving(false);
        }
      },
    });
  };

  const handleApprove = (record: API.RefundRequest) => {
    const isOrganization = record.OrderType === 'organization';
    const isCancelledRegistration =
      isOrganization && record.OrderSnapshot?.RegistrationStatus === 2;
    const isRetry = record.Status === 'refund_failed';
    Modal.confirm({
      title: isOrganization
        ? isRetry
          ? '重试组局意向金退款？'
          : isCancelledRegistration
          ? '确认退款已取消报名？'
          : '确认用户到店并退款？'
        : isRetry
        ? '重试退款？'
        : '通过退款申请？',
      content: isOrganization ? (
        <Space direction="vertical" size={4}>
          <Text>用户：{record.User?.NickName || '-'}</Text>
          <Text>
            活动：
            {record.OrderSnapshot?.ActivityTitle ||
              record.OrderSnapshot?.Title ||
              `活动 ${record.OrderSnapshot?.ActivityId || '-'}`}
          </Text>
          <Text>退款金额：{formatPrice(record.Amount)}</Text>
          <Text type="secondary">
            {isCancelledRegistration
              ? '该用户已取消报名，不代表已到店；确认后仍会将意向金微信原路退款。'
              : '确认后将调用微信支付，把该笔组局意向金微信原路退款。'}
          </Text>
        </Space>
      ) : (
        '确认后将调用微信支付发起原路退款，请先核对订单状态和退款金额。'
      ),
      okText: isRetry
        ? '确认重试退款'
        : isOrganization
        ? isCancelledRegistration
          ? '确认原路退款'
          : '确认到店并退款'
        : '通过并退款',
      cancelText: '取消',
      onOk: async () => {
        setApprovingId(record.Id);
        try {
          const response = await approveRefundRequest(record.Id);
          if (response.Code === 0) {
            message.success(response.Message || '已发起微信退款');
            actionRef.current?.reload();
          } else {
            message.error(response.Msg || response.Message || '操作失败');
          }
        } finally {
          setApprovingId(undefined);
        }
      },
    });
  };

  const handleReject = (record: API.RefundRequest) => {
    const isOrganization = record.OrderType === 'organization';
    let remark = '';
    Modal.confirm({
      title: isOrganization ? '标记该意向金不退款？' : '拒绝退款申请',
      content: (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text type="secondary">
            {isOrganization
              ? '确认后该报名将标记为不退款，原因会作为审核备注记录。'
              : '拒绝原因会作为审核备注记录。'}
          </Text>
          <Input.TextArea
            rows={3}
            placeholder={isOrganization ? '请输入不退款原因' : '请输入拒绝原因'}
            onChange={(event) => {
              remark = event.target.value;
            }}
          />
        </Space>
      ),
      okText: isOrganization ? '确认不退款' : '确认拒绝',
      cancelText: '取消',
      onOk: async () => {
        if (!remark.trim()) {
          message.warning(
            isOrganization ? '请填写不退款原因' : '请填写拒绝原因',
          );
          return Promise.reject();
        }
        setRejectingId(record.Id);
        try {
          const response = await rejectRefundRequest(record.Id, {
            Remark: remark.trim(),
          });
          if (response.Code === 0) {
            message.success(
              response.Message ||
                (isOrganization ? '已标记为不退款' : '已拒绝退款申请'),
            );
            actionRef.current?.reload();
          } else {
            message.error(response.Msg || response.Message || '操作失败');
          }
        } finally {
          setRejectingId(undefined);
        }
      },
    });
  };

  const columns: ProColumns<API.RefundRequest>[] = [
    {
      title: '退款申请',
      dataIndex: 'Id',
      width: 130,
      search: false,
      render: (_, record) => (
        <div className="refund-stack">
          <Text strong>#{record.Id}</Text>
          <Tag color={getOrderTypeMeta(record).color}>
            {getOrderTypeMeta(record).text}
          </Tag>
        </div>
      ),
    },
    {
      title: '订单类型',
      dataIndex: 'OrderType',
      hideInTable: true,
      valueEnum: {
        play: { text: '玩乐' },
        catering: { text: '吃喝' },
        organization: { text: '组局意向金' },
      },
      render: (_, record) => {
        const meta = getOrderTypeMeta(record);
        return <Tag color={meta.color}>{meta.text}</Tag>;
      },
    },
    {
      title: '订单信息',
      dataIndex: 'OrderId',
      width: 300,
      search: false,
      render: (_, record) => (
        <div className="refund-order-info refund-stack">
          <Text strong className="refund-order-title">
            {getOrderTitle(record)}
          </Text>
          {record.OrderType === 'organization' && (
            <>
              <Text type="secondary">
                {record.OrderSnapshot?.StoreName || '门店未记录'}
              </Text>
              <Text type="secondary">
                活动：{formatTime(record.OrderSnapshot?.ActivityStartTime)}
              </Text>
            </>
          )}
          <Text type="secondary">
            {record.OrderSnapshot?.StatusText || '—'}
          </Text>
        </div>
      ),
    },
    {
      title: '用户',
      dataIndex: 'Keyword',
      width: 170,
      render: (_, record) => (
        <div className="refund-stack">
          <Text>{record.User?.NickName || '-'}</Text>
          <Text type="secondary" className="refund-phone">
            {record.User?.Phone || '-'}
          </Text>
        </div>
      ),
    },
    {
      title: '退款金额',
      dataIndex: 'Amount',
      width: 120,
      search: false,
      render: (_, record) => <Text strong>{formatPrice(record.Amount)}</Text>,
    },
    {
      title: '状态',
      dataIndex: 'Status',
      width: 154,
      valueEnum: Object.fromEntries(
        Object.entries(statusMeta).map(([key, value]) => [
          key,
          { text: value.text },
        ]),
      ),
      render: (_, record) => {
        const meta = getStatusMeta(record);
        return <Tag color={meta.color}>{meta.text}</Tag>;
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 184,
      fixed: 'right',
      search: false,
      render: (_, record) => {
        if (record.Status === 'refund_failed') {
          return (
            <Button
              type="primary"
              danger
              disabled={batchApproving}
              loading={approvingId === record.Id}
              onClick={() => handleApprove(record)}
            >
              重试
            </Button>
          );
        }
        if (record.Status !== 'pending_review') {
          return null;
        }
        const isOrganization = record.OrderType === 'organization';
        return (
          <Space>
            <Button
              type="primary"
              disabled={batchApproving}
              loading={approvingId === record.Id}
              onClick={() => handleApprove(record)}
            >
              {isOrganization ? '退款' : '通过'}
            </Button>
            <Button
              danger
              disabled={batchApproving}
              loading={rejectingId === record.Id}
              onClick={() => handleReject(record)}
            >
              {isOrganization ? '不退款' : '拒绝'}
            </Button>
          </Space>
        );
      },
    },
  ];

  return (
    <PageContainer>
      <ProTable<API.RefundRequest>
        headerTitle="退款管理"
        actionRef={actionRef}
        rowKey="Id"
        columns={columns}
        className="refund-table"
        search={{ labelWidth: 'auto', defaultCollapsed: false }}
        expandable={{
          expandRowByClick: false,
          expandIcon: ({ expanded, onExpand, record }) => (
            <Button
              type="text"
              aria-label={`${expanded ? '收起' : '查看'}申请 ${
                record.Id
              } 的详情`}
              aria-expanded={expanded}
              onClick={(event) => onExpand(record, event)}
            >
              {expanded ? '收起' : '详情'}
            </Button>
          ),
          expandedRowRender: (record) => (
            <div className="refund-details">
              <div className="refund-detail-wide">
                <Text type="secondary">订单信息</Text>
                <div>{getOrderTitle(record)}</div>
              </div>
              <div>
                <Text type="secondary">订单 ID</Text>
                <div>{record.OrderId}</div>
              </div>
              <div>
                <Text type="secondary">支付时间</Text>
                <div>{formatTime(record.PayOrder?.PayEndTime)}</div>
              </div>
              <div>
                <Text type="secondary">申请时间</Text>
                <div>{formatTime(record.CreatedAt)}</div>
              </div>
              <div>
                <Text type="secondary">审核时间</Text>
                <div>{formatTime(record.ReviewedAt)}</div>
              </div>
              <div className="refund-detail-wide">
                <Text type="secondary">审核备注</Text>
                <div>{record.ReviewRemark || '—'}</div>
              </div>
              {record.RefundError && (
                <div className="refund-detail-wide">
                  <Text type="danger">退款失败原因</Text>
                  <div>{record.RefundError}</div>
                </div>
              )}
            </div>
          ),
        }}
        rowSelection={{
          selectedRowKeys,
          getCheckboxProps: (record) => ({
            disabled: batchApproving || !canBatchRefund(record),
            title: canBatchRefund(record)
              ? undefined
              : '仅支持选择已报名、待到店退款的组局记录',
          }),
          onChange: (keys, rows) => {
            setSelectedRowKeys(keys);
            setSelectedRows(rows);
          },
        }}
        toolBarRender={() => [
          <Button
            key="batch-refund"
            type="primary"
            disabled={selectedRows.length === 0}
            loading={batchApproving}
            onClick={handleBatchApprove}
          >
            批量退款 {selectedRows.length || ''}
          </Button>,
        ]}
        request={async (params) => {
          const response = await queryRefundRequests({
            current: params.current,
            pageSize: params.pageSize,
            Status: params.Status as API.RefundRequestStatus,
            OrderType: params.OrderType as API.RefundOrderType,
            Keyword: params.Keyword,
          });

          if (response.Code === 0) {
            return {
              data: response.Data?.Items || [],
              total: response.Data?.Total || 0,
              success: true,
            };
          }

          message.error(response.Msg || response.Message || '获取退款申请失败');
          return {
            data: [],
            total: 0,
            success: false,
          };
        }}
        pagination={{
          showQuickJumper: true,
          showSizeChanger: true,
          defaultPageSize: 20,
        }}
      />
    </PageContainer>
  );
};

export default RefundsPage;
