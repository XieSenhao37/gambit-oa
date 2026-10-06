import { ProTable } from '@/components/AdaptiveTable';
import {
  addDishStoreItem,
  deleteDishStoreItem,
  queryDishes,
  queryDishLibrary,
  updateDishStatus,
  updateDishStoreItem,
} from '@/services/dish';
import { cosThumb } from '@/utils/cosImage';
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
  Image,
  InputNumber,
  message,
  Popconfirm,
  Select,
  Space,
  Switch,
  Tag,
} from 'antd';
import { useRef, useState } from 'react';

const formatPrice = (cents?: number) => {
  if (!cents) return '0.00';
  return (cents / 100).toFixed(2);
};

const DishPage: React.FC = () => {
  const actionRef = useRef<ActionType>();
  const [form] = Form.useForm();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<API.DishItem | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [statusLoadingId, setStatusLoadingId] = useState<number>();
  const [categories, setCategories] = useState<API.DishCategory[]>([]);
  const [libraryItems, setLibraryItems] = useState<API.DishLibraryItem[]>([]);
  const [libraryLoading, setLibraryLoading] = useState(false);

  const loadLibraryItems = async (keyword?: string) => {
    setLibraryLoading(true);
    try {
      const response = await queryDishLibrary({
        current: 1,
        pageSize: 100,
        Keyword: keyword,
      });
      if (response.Code === 0) {
        setLibraryItems(response.Data?.Items || []);
      }
    } finally {
      setLibraryLoading(false);
    }
  };

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ Status: 1, Sort: 0 });
    loadLibraryItems();
    setDrawerOpen(true);
  };

  const openEdit = (record: API.DishItem) => {
    setEditing(record);
    if (record.LibraryItemId) {
      setLibraryItems([
        {
          Id: record.LibraryItemId,
          Name: record.Name,
          Description: record.Description,
          DefaultPrice: record.DefaultPrice || record.Price,
          ImageUrl: record.ImageUrl,
          CategoryIds: record.CategoryIds,
          Options: record.Options,
          Tags: record.Tags,
        },
      ]);
    }
    form.setFieldsValue({
      LibraryItemId: record.LibraryItemId,
      Price: record.Price / 100,
      Status: record.Status,
      Sort: record.Sort || 0,
    });
    setDrawerOpen(true);
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
    setEditing(null);
    form.resetFields();
  };

  const handleStatusChange = async (
    record: API.DishItem,
    nextStatus: 0 | 1,
  ) => {
    setStatusLoadingId(record.Id);
    try {
      const response = await updateDishStatus(record.Id, {
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

  const handleRemove = async (record: API.DishItem) => {
    const response = await deleteDishStoreItem(record.Id);
    if (response.Code === 0) {
      message.success('已从当前门店菜单移除');
      actionRef.current?.reload();
    } else {
      message.error(response.Message || '移除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload = {
        LibraryItemId: Number(values.LibraryItemId),
        Price: Math.round(Number(values.Price) * 100),
        Status: (values.Status ?? 1) as 0 | 1,
        Sort: Number(values.Sort || 0),
      };

      setSubmitting(true);
      const response = editing
        ? await updateDishStoreItem(editing.Id, payload)
        : await addDishStoreItem(payload);

      if (response.Code === 0) {
        message.success(editing ? '更新成功' : '已添加到当前门店菜单');
        closeDrawer();
        actionRef.current?.reload();
      } else {
        message.error(response.Message || '保存失败');
      }
    } catch (error: any) {
      if (error?.errorFields) {
        // 表单校验失败，AntD 已自动高亮
        return;
      }
      message.error(error?.message || '保存失败');
    } finally {
      setSubmitting(false);
    }
  };

  const renderCategoryNames = (ids: number[] = []) => {
    return ids
      .map((id) => categories.find((c) => c.Id === id)?.Name)
      .filter(Boolean) as string[];
  };

  const columns: ProColumns<API.DishItem>[] = [
    {
      title: 'ID',
      dataIndex: 'Id',
      width: 80,
      search: false,
    },
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
      width: 160,
      fieldProps: { placeholder: '搜索餐品名称' },
    },
    {
      title: '分类',
      dataIndex: 'CategoryIds',
      width: 200,
      search: false,
      render: (_, record) => (
        <Space wrap size={[4, 4]}>
          {renderCategoryNames(record.CategoryIds).map((name) => (
            <Tag key={name}>{name}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '价格',
      dataIndex: 'Price',
      width: 100,
      search: false,
      render: (_, record) => `¥${formatPrice(record.Price)}`,
    },
    {
      title: '标签',
      dataIndex: 'Tags',
      width: 160,
      search: false,
      render: (_, record) => (
        <Space wrap size={[4, 4]}>
          {(record.Tags || []).map((tag) => (
            <Tag color="gold" key={tag}>
              {tag}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'Status',
      width: 110,
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
      title: '更新时间',
      dataIndex: 'UpdatedAt',
      width: 170,
      search: false,
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
            title="确认从当前门店菜单移除？"
            onConfirm={() => handleRemove(record)}
            okText="确认"
            cancelText="取消"
          >
            <Button danger type="link">
              移除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <PageContainer>
      <ProTable<API.DishItem>
        headerTitle="门店菜单"
        actionRef={actionRef}
        rowKey="Id"
        scroll={{ x: 1200 }}
        search={{ labelWidth: 'auto', defaultCollapsed: false }}
        toolBarRender={() => [
          <Button
            key="create"
            type="primary"
            icon={<PlusOutlined />}
            onClick={openCreate}
          >
            从餐品库添加
          </Button>,
        ]}
        request={async (params) => {
          const response = await queryDishes({
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
        title={
          editing ? `编辑门店菜单项 #${editing.Id}` : '从餐品库添加到当前门店'
        }
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
          <Form.Item
            label="餐品信息库餐品"
            name="LibraryItemId"
            rules={[{ required: true, message: '请选择餐品' }]}
          >
            <Select
              showSearch
              disabled={!!editing}
              loading={libraryLoading}
              placeholder="搜索并选择餐品"
              filterOption={false}
              onSearch={loadLibraryItems}
              onSelect={(value) => {
                const selected = libraryItems.find((item) => item.Id === value);
                if (selected && !editing) {
                  form.setFieldsValue({
                    Price: selected.DefaultPrice / 100,
                  });
                }
              }}
              options={libraryItems.map((item) => ({
                label: `${item.Name}（默认 ¥${formatPrice(
                  item.DefaultPrice,
                )}）`,
                value: item.Id,
              }))}
            />
          </Form.Item>

          <Form.Item
            label="当前门店售价（元）"
            name="Price"
            rules={[{ required: true, message: '请输入价格' }]}
          >
            <InputNumber
              min={0}
              precision={2}
              step={0.5}
              style={{ width: '100%' }}
              placeholder="如：18.00"
              addonBefore="¥"
            />
          </Form.Item>

          <Form.Item label="排序" name="Sort" tooltip="数值越小越靠前">
            <InputNumber min={0} precision={0} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item label="上下架" name="Status">
            <Select
              options={[
                { label: '上架', value: 1 },
                { label: '下架', value: 0 },
              ]}
            />
          </Form.Item>
        </Form>
      </Drawer>
    </PageContainer>
  );
};

export default DishPage;
