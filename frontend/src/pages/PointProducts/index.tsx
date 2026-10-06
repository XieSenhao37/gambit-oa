import { ProTable } from '@/components/AdaptiveTable';
import {
  createPointProduct,
  deletePointProduct,
  queryPointProducts,
  updatePointProduct,
  updatePointProductStatus,
} from '@/services/point';
import { cosThumb } from '@/utils/cosImage';
import { PlusOutlined, UploadOutlined } from '@ant-design/icons';
import {
  PageContainer,
  type ActionType,
  type ProColumns,
} from '@ant-design/pro-components';
import {
  Button,
  DatePicker,
  Drawer,
  Form,
  Image,
  Input,
  InputNumber,
  message,
  Popconfirm,
  Select,
  Space,
  Switch,
  Tag,
  Upload,
  type UploadFile,
} from 'antd';
import dayjs, { type Dayjs } from 'dayjs';
import { useRef, useState } from 'react';

const formatYuan = (cents?: number | null) => {
  if (!cents) return '0.00';
  return (cents / 100).toFixed(2);
};

const hasValue = <T,>(value: T | null | undefined): value is T =>
  value !== null && value !== undefined;

type PublishMode = 'offline' | 'immediate' | 'scheduled';

const getPublishMode = (record: API.PointProductItem): PublishMode => {
  if (record.Status === 0) return 'offline';
  if (record.RedeemStartAt && dayjs(record.RedeemStartAt).isAfter(dayjs())) {
    return 'scheduled';
  }
  return 'immediate';
};

const PointProductsPage: React.FC = () => {
  const actionRef = useRef<ActionType>();
  const [form] = Form.useForm();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<API.PointProductItem | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [statusLoadingId, setStatusLoadingId] = useState<number>();
  const [categories, setCategories] = useState<API.PointCategoryItem[]>([]);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const publishMode = Form.useWatch<PublishMode>('PublishMode', form);

  const openCreate = () => {
    setEditing(null);
    setFileList([]);
    form.resetFields();
    form.setFieldsValue({
      Sort: 0,
      Stock: -1,
      PublishMode: 'offline',
      MaxRedeemPerUser: -1,
    });
    setDrawerOpen(true);
  };

  const openEdit = (record: API.PointProductItem) => {
    setEditing(record);
    setFileList(
      record.ImageUrl
        ? [
            {
              uid: 'existing',
              name: 'image',
              status: 'done',
              url: cosThumb(record.ImageUrl, 'sm'),
              thumbUrl: cosThumb(record.ImageUrl, 'sm'),
            } as UploadFile,
          ]
        : [],
    );
    form.setFieldsValue({
      Name: record.Name,
      CategoryId: record.CategoryId ?? undefined,
      PointsPrice: record.PointsPrice,
      SettlementPrice: hasValue(record.SettlementPrice)
        ? record.SettlementPrice / 100
        : undefined,
      OriginalPrice: hasValue(record.OriginalPrice)
        ? record.OriginalPrice / 100
        : undefined,
      Stock: record.Stock,
      Sort: record.Sort,
      Description: record.Description,
      PublishMode: getPublishMode(record),
      RedeemStartAt: record.RedeemStartAt
        ? dayjs(record.RedeemStartAt)
        : undefined,
      MaxRedeemPerUser: record.MaxRedeemPerUser ?? -1,
    });
    setDrawerOpen(true);
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
    setEditing(null);
    setFileList([]);
    form.resetFields();
  };

  const handleStatusChange = async (
    record: API.PointProductItem,
    nextStatus: 0 | 1,
  ) => {
    setStatusLoadingId(record.Id);
    try {
      const response = await updatePointProductStatus(record.Id, {
        Status: nextStatus,
      });
      if (response.Code === 0) {
        message.success(nextStatus === 1 ? '已上架' : '已下架');
        actionRef.current?.reload();
      } else {
        message.error(response.Message || '操作失败');
      }
    } finally {
      setStatusLoadingId(undefined);
    }
  };

  const handleDelete = async (record: API.PointProductItem) => {
    const response = await deletePointProduct(record.Id);
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
      const formData = new FormData();
      formData.append('Name', values.Name);
      formData.append(
        'PointsPrice',
        String(Math.round(Number(values.PointsPrice))),
      );
      formData.append(
        'CategoryId',
        hasValue(values.CategoryId) ? String(values.CategoryId) : '',
      );
      formData.append('Description', values.Description || '');
      formData.append(
        'SettlementPrice',
        hasValue(values.SettlementPrice)
          ? String(Math.round(Number(values.SettlementPrice) * 100))
          : '',
      );
      formData.append(
        'OriginalPrice',
        hasValue(values.OriginalPrice) && values.OriginalPrice !== ''
          ? String(Math.round(Number(values.OriginalPrice) * 100))
          : '',
      );
      formData.append(
        'Stock',
        String(hasValue(values.Stock) ? Number(values.Stock) : -1),
      );
      formData.append('Sort', String(Number(values.Sort || 0)));
      formData.append('Status', values.PublishMode === 'offline' ? '0' : '1');
      formData.append(
        'RedeemStartAt',
        values.PublishMode === 'scheduled'
          ? String((values.RedeemStartAt as Dayjs).valueOf())
          : '',
      );
      formData.append(
        'MaxRedeemPerUser',
        String(
          hasValue(values.MaxRedeemPerUser)
            ? Number(values.MaxRedeemPerUser)
            : -1,
        ),
      );

      const newFile = fileList.find((f) => f.originFileObj);
      if (newFile?.originFileObj) {
        formData.append('Image', newFile.originFileObj as Blob);
      } else if (!editing) {
        message.error('请上传商品图片');
        return;
      }

      setSubmitting(true);
      const response = editing
        ? await updatePointProduct(editing.Id, formData)
        : await createPointProduct(formData);

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

  const columns: ProColumns<API.PointProductItem>[] = [
    { title: 'ID', dataIndex: 'Id', width: 70, search: false },
    {
      title: '图片',
      dataIndex: 'ImageUrl',
      width: 90,
      search: false,
      render: (_, record) =>
        record.ImageUrl ? (
          <Image
            src={cosThumb(record.ImageUrl, 'xs')}
            preview={{ src: cosThumb(record.ImageUrl, 'lg') }}
            alt={record.Name}
            width={64}
            height={64}
            style={{ objectFit: 'cover', borderRadius: 4 }}
          />
        ) : (
          <span style={{ color: '#bbb' }}>无</span>
        ),
    },
    {
      title: '名称',
      dataIndex: 'Name',
      width: 180,
      fieldProps: { placeholder: '搜索商品名称' },
    },
    {
      title: '分类',
      dataIndex: 'CategoryName',
      width: 120,
      search: false,
      render: (_, record) =>
        record.CategoryName ? (
          <Tag>{record.CategoryName}</Tag>
        ) : (
          <span style={{ color: '#bbb' }}>未分类</span>
        ),
    },
    {
      title: '所需积分',
      dataIndex: 'PointsPrice',
      width: 100,
      search: false,
      render: (_, record) => <Tag color="blue">{record.PointsPrice} 积分</Tag>,
    },
    {
      title: '市场参考价',
      dataIndex: 'OriginalPrice',
      width: 110,
      search: false,
      render: (_, record) =>
        record.OriginalPrice ? (
          `¥${formatYuan(record.OriginalPrice)}`
        ) : (
          <span style={{ color: '#bbb' }}>—</span>
        ),
    },
    {
      title: '预估单件结算价',
      dataIndex: 'SettlementPrice',
      width: 150,
      search: false,
      render: (_, record) =>
        hasValue(record.SettlementPrice) ? (
          `¥${formatYuan(record.SettlementPrice)}`
        ) : (
          <Tag>待总部补充</Tag>
        ),
    },
    {
      title: '库存',
      dataIndex: 'Stock',
      width: 90,
      search: false,
      render: (_, record) => (record.Stock < 0 ? '不限' : record.Stock),
    },
    {
      title: '每人限兑',
      dataIndex: 'MaxRedeemPerUser',
      width: 100,
      search: false,
      render: (_, record) =>
        record.MaxRedeemPerUser < 0 ? '不限' : `${record.MaxRedeemPerUser} 件`,
    },
    {
      title: '开兑时间',
      dataIndex: 'RedeemStartAt',
      width: 170,
      search: false,
      render: (_, record) =>
        record.RedeemStartAt ? (
          record.RedeemStartAt
        ) : (
          <span style={{ color: '#999' }}>立即开兑</span>
        ),
    },
    { title: '排序', dataIndex: 'Sort', width: 70, search: false },
    {
      title: '状态',
      dataIndex: 'Status',
      width: 100,
      search: false,
      render: (_, record) => (
        <Switch
          checked={record.Status === 1}
          checkedChildren="上架"
          unCheckedChildren="下架"
          loading={statusLoadingId === record.Id}
          onChange={(checked) => handleStatusChange(record, checked ? 1 : 0)}
        />
      ),
    },
    {
      title: '操作',
      width: 140,
      fixed: 'right',
      key: 'action',
      search: false,
      render: (_, record) => (
        <Space>
          <Button type="link" onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm
            title="确认删除该商品？"
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
      <ProTable<API.PointProductItem>
        headerTitle="积分商品列表"
        actionRef={actionRef}
        rowKey="Id"
        scroll={{ x: 1500 }}
        search={{ labelWidth: 'auto', defaultCollapsed: false }}
        toolBarRender={() => [
          <Button
            key="create"
            type="primary"
            icon={<PlusOutlined />}
            onClick={openCreate}
          >
            新增商品
          </Button>,
        ]}
        request={async (params) => {
          const response = await queryPointProducts({
            current: params.current,
            pageSize: params.pageSize,
            Keyword: params.Name,
          });
          if (response.Code === 0 && response.Data) {
            setCategories(response.Data.Categories || []);
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

      <Drawer
        title={editing ? `编辑商品 #${editing.Id}` : '新增商品'}
        width={520}
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
          <Form.Item label="商品图片" required>
            <Upload
              listType="picture-card"
              maxCount={1}
              fileList={fileList}
              beforeUpload={() => false}
              onChange={({ fileList: next }) => setFileList(next)}
              onRemove={() => {
                setFileList([]);
                return true;
              }}
              accept="image/jpeg,image/png,image/webp,image/gif"
            >
              {fileList.length === 0 && (
                <div>
                  <UploadOutlined />
                  <div style={{ marginTop: 8 }}>上传图片</div>
                </div>
              )}
            </Upload>
            <div style={{ color: '#999', fontSize: 12 }}>
              支持 jpg/png/webp/gif，最大 5MB
            </div>
          </Form.Item>

          <Form.Item
            label="商品名称"
            name="Name"
            rules={[
              { required: true, message: '请输入商品名称' },
              { max: 120, message: '最多 120 字' },
            ]}
          >
            <Input placeholder="如：KEEPCUP 即饮杯" />
          </Form.Item>

          <Form.Item
            label="分类"
            name="CategoryId"
            rules={[{ required: true, message: '请选择分类' }]}
          >
            <Select
              placeholder="选择一级分类"
              options={categories.map((c) => ({ label: c.Name, value: c.Id }))}
              allowClear
            />
          </Form.Item>

          <Form.Item
            label="兑换所需积分"
            name="PointsPrice"
            rules={[{ required: true, message: '请输入兑换所需积分' }]}
          >
            <InputNumber
              min={0}
              precision={0}
              step={10}
              style={{ width: '100%' }}
              placeholder="如：500"
            />
          </Form.Item>

          <Form.Item
            label="市场参考价（元）"
            name="OriginalPrice"
            tooltip="可空，用于展示“价值 ¥xx”"
          >
            <InputNumber
              min={0}
              precision={2}
              step={1}
              style={{ width: '100%' }}
              placeholder="如：368.00"
              addonBefore="¥"
            />
          </Form.Item>

          <Form.Item
            label="单件结算价（元，选填）"
            name="SettlementPrice"
            extra="不确定可留空，不影响上架和兑换。仅供内部结算，最终由总部在 OA 修改、补充并确认；不改变已生成的成本单。"
          >
            <InputNumber
              min={0}
              max={1000000}
              precision={2}
              style={{ width: '100%' }}
              placeholder="留空待总部确认；0 表示零成本"
              addonBefore="¥"
            />
          </Form.Item>

          <Form.Item label="库存" name="Stock" tooltip="-1 表示不限库存">
            <InputNumber
              min={-1}
              precision={0}
              style={{ width: '100%' }}
              placeholder="-1 表示不限"
            />
          </Form.Item>

          <Form.Item
            label="每人限兑"
            name="MaxRedeemPerUser"
            tooltip="-1 表示不限；有限额时须至少为 1"
            rules={[
              { required: true, message: '请输入每人限兑数量' },
              {
                validator: (_, value) =>
                  value === -1 || value >= 1
                    ? Promise.resolve()
                    : Promise.reject(
                        new Error('请输入 -1（不限）或大于等于 1 的整数'),
                      ),
              },
            ]}
          >
            <InputNumber
              min={-1}
              precision={0}
              style={{ width: '100%' }}
              placeholder="-1 表示不限"
            />
          </Form.Item>

          <Form.Item
            label="上架方式"
            name="PublishMode"
            rules={[{ required: true, message: '请选择上架方式' }]}
          >
            <Select
              options={[
                { label: '暂不上架', value: 'offline' },
                { label: '立即上架', value: 'immediate' },
                { label: '定时上架', value: 'scheduled' },
              ]}
            />
          </Form.Item>

          {publishMode === 'scheduled' && (
            <Form.Item
              label="开兑日期时间"
              name="RedeemStartAt"
              rules={[
                { required: true, message: '请选择开兑日期时间' },
                {
                  validator: (_, value: Dayjs | undefined) =>
                    value && value.isAfter(dayjs())
                      ? Promise.resolve()
                      : Promise.reject(new Error('开兑时间必须晚于当前时间')),
                },
              ]}
            >
              <DatePicker
                showTime={{ format: 'HH:mm:ss' }}
                format="YYYY-MM-DD HH:mm:ss"
                style={{ width: '100%' }}
                placeholder="选择未来的开兑时间"
                disabledDate={(current) =>
                  current && current.endOf('day').isBefore(dayjs())
                }
              />
            </Form.Item>
          )}

          <Form.Item label="排序" name="Sort" tooltip="越小越靠前">
            <InputNumber
              min={0}
              precision={0}
              style={{ width: '100%' }}
              placeholder="0"
            />
          </Form.Item>

          <Form.Item label="描述" name="Description">
            <Input.TextArea rows={3} maxLength={255} showCount />
          </Form.Item>
        </Form>
      </Drawer>
    </PageContainer>
  );
};

export default PointProductsPage;
