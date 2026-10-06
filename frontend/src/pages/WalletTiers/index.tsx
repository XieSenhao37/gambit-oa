import { ProTable } from '@/components/AdaptiveTable';
import {
  createWalletTier,
  deleteWalletTier,
  queryWalletTiers,
  updateWalletTier,
  updateWalletTierStatus,
} from '@/services/wallet';
import { PlusOutlined } from '@ant-design/icons';
import {
  PageContainer,
  type ActionType,
  type ProColumns,
} from '@ant-design/pro-components';
import {
  Button,
  Drawer,
  Form,
  Input,
  InputNumber,
  message,
  Popconfirm,
  Space,
  Switch,
  Tag,
} from 'antd';
import { useRef, useState } from 'react';

const formatYuan = (cents?: number) => {
  if (!cents) return '0.00';
  return (cents / 100).toFixed(2);
};

const WalletTiersPage: React.FC = () => {
  const actionRef = useRef<ActionType>();
  const [form] = Form.useForm();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<API.WalletTierItem | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [statusLoadingId, setStatusLoadingId] = useState<number>();

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ Sort: 0, Enabled: 1, BonusAmount: 0 });
    setDrawerOpen(true);
  };

  const openEdit = (record: API.WalletTierItem) => {
    setEditing(record);
    form.setFieldsValue({
      Amount: record.Amount / 100,
      BonusAmount: record.BonusAmount / 100,
      Label: record.Label,
      Sort: record.Sort,
      Enabled: record.Enabled,
    });
    setDrawerOpen(true);
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
    setEditing(null);
    form.resetFields();
  };

  const handleStatusChange = async (
    record: API.WalletTierItem,
    nextEnabled: 0 | 1,
  ) => {
    setStatusLoadingId(record.Id);
    try {
      const response = await updateWalletTierStatus(record.Id, {
        Enabled: nextEnabled,
      });
      if (response.Code === 0) {
        message.success(nextEnabled === 1 ? '已启用' : '已停用');
        actionRef.current?.reload();
      } else {
        message.error(response.Message || '操作失败');
      }
    } finally {
      setStatusLoadingId(undefined);
    }
  };

  const handleDelete = async (record: API.WalletTierItem) => {
    const response = await deleteWalletTier(record.Id);
    if (response.Code === 0) {
      message.success('删除成功');
      actionRef.current?.reload();
    } else {
      message.error(response.Message || '删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload: API.SaveWalletTierParams = {
        Amount: Math.round(Number(values.Amount) * 100),
        BonusAmount: Math.round(Number(values.BonusAmount || 0) * 100),
        Label: (values.Label || '').trim(),
        Sort: Number(values.Sort || 0),
        Enabled: values.Enabled ? 1 : 0,
      };

      setSubmitting(true);
      const response = editing
        ? await updateWalletTier(editing.Id, payload)
        : await createWalletTier(payload);

      if (response.Code === 0) {
        message.success(editing ? '更新成功' : '创建成功');
        closeDrawer();
        actionRef.current?.reload();
      } else {
        message.error(response.Message || '保存失败');
      }
    } catch (error: any) {
      if (error?.errorFields) {
        return;
      }
      message.error(error?.message || '保存失败');
    } finally {
      setSubmitting(false);
    }
  };

  const columns: ProColumns<API.WalletTierItem>[] = [
    {
      title: 'ID',
      dataIndex: 'Id',
      width: 80,
    },
    {
      title: '充值金额',
      dataIndex: 'Amount',
      width: 120,
      render: (_, record) => `¥${formatYuan(record.Amount)}`,
    },
    {
      title: '赠送金额',
      dataIndex: 'BonusAmount',
      width: 120,
      render: (_, record) =>
        record.BonusAmount > 0 ? (
          <Tag color="blue">送 ¥{formatYuan(record.BonusAmount)}</Tag>
        ) : (
          <span style={{ color: '#bbb' }}>无</span>
        ),
    },
    {
      title: '展示文案',
      dataIndex: 'Label',
      width: 160,
      render: (_, record) =>
        record.Label || <span style={{ color: '#bbb' }}>未设置</span>,
    },
    {
      title: '排序',
      dataIndex: 'Sort',
      width: 80,
    },
    {
      title: '状态',
      dataIndex: 'Enabled',
      width: 110,
      render: (_, record) => (
        <Switch
          checked={record.Enabled === 1}
          checkedChildren="启用"
          unCheckedChildren="停用"
          loading={statusLoadingId === record.Id}
          onChange={(checked) => handleStatusChange(record, checked ? 1 : 0)}
        />
      ),
    },
    {
      title: '更新时间',
      dataIndex: 'UpdatedAt',
      width: 170,
    },
    {
      title: '操作',
      width: 140,
      fixed: 'right',
      key: 'action',
      render: (_, record) => (
        <Space>
          <Button type="link" onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm
            title="确认删除该档位？"
            onConfirm={() => handleDelete(record)}
            okText="删除"
            cancelText="取消"
          >
            <Button type="link" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <PageContainer>
      <ProTable<API.WalletTierItem>
        headerTitle="充值档位"
        actionRef={actionRef}
        rowKey="Id"
        scroll={{ x: 1000 }}
        search={false}
        toolBarRender={() => [
          <Button
            key="create"
            type="primary"
            icon={<PlusOutlined />}
            onClick={openCreate}
          >
            新增档位
          </Button>,
        ]}
        request={async (params) => {
          const response = await queryWalletTiers({
            current: params.current,
            pageSize: params.pageSize,
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
          showSizeChanger: true,
          defaultPageSize: 20,
          pageSizeOptions: ['10', '20', '50'],
        }}
      />

      <Drawer
        title={editing ? `编辑档位 #${editing.Id}` : '新增档位'}
        width={460}
        open={drawerOpen}
        onClose={closeDrawer}
        destroyOnClose
        extra={
          <Space>
            <Button onClick={closeDrawer}>取消</Button>
            {editing ? (
              <Popconfirm
                title="确认更新？"
                onConfirm={handleSubmit}
                okText="确认"
                cancelText="取消"
              >
                <Button type="primary" loading={submitting}>
                  保存
                </Button>
              </Popconfirm>
            ) : (
              <Button
                type="primary"
                loading={submitting}
                onClick={handleSubmit}
              >
                创建
              </Button>
            )}
          </Space>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="充值金额（元）"
            name="Amount"
            rules={[{ required: true, message: '请输入充值金额' }]}
            tooltip="小程序按此金额匹配赠送，需在 1 元至 5000 元之间"
          >
            <InputNumber
              min={1}
              max={5000}
              precision={2}
              step={10}
              style={{ width: '100%' }}
              placeholder="如：100.00"
              addonBefore="¥"
            />
          </Form.Item>

          <Form.Item
            label="赠送金额（元）"
            name="BonusAmount"
            tooltip="0 表示该档位无赠送"
          >
            <InputNumber
              min={0}
              precision={2}
              step={5}
              style={{ width: '100%' }}
              placeholder="如：10.00"
              addonBefore="¥"
            />
          </Form.Item>

          <Form.Item
            label="展示文案"
            name="Label"
            tooltip="可空，用于小程序档位副标题"
          >
            <Input maxLength={64} placeholder="如：超值首选" />
          </Form.Item>

          <Form.Item label="排序" name="Sort" tooltip="越小越靠前">
            <InputNumber min={0} style={{ width: '100%' }} placeholder="0" />
          </Form.Item>

          <Form.Item label="启用" name="Enabled" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Drawer>
    </PageContainer>
  );
};

export default WalletTiersPage;
