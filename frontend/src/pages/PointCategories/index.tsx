import { ProTable } from '@/components/AdaptiveTable';
import {
  createPointCategory,
  deletePointCategory,
  queryPointCategories,
  updatePointCategory,
  updatePointCategoryStatus,
} from '@/services/point';
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
} from 'antd';
import { useRef, useState } from 'react';

const PointCategoriesPage: React.FC = () => {
  const actionRef = useRef<ActionType>();
  const [form] = Form.useForm();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<API.PointCategoryItem | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [statusLoadingId, setStatusLoadingId] = useState<number>();

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ Sort: 0, Status: 1 });
    setDrawerOpen(true);
  };

  const openEdit = (record: API.PointCategoryItem) => {
    setEditing(record);
    form.setFieldsValue({
      Name: record.Name,
      Sort: record.Sort,
      Status: record.Status,
    });
    setDrawerOpen(true);
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
    setEditing(null);
    form.resetFields();
  };

  const handleStatusChange = async (
    record: API.PointCategoryItem,
    nextStatus: 0 | 1,
  ) => {
    setStatusLoadingId(record.Id);
    try {
      const response = await updatePointCategoryStatus(record.Id, {
        Status: nextStatus,
      });
      if (response.Code === 0) {
        message.success(nextStatus === 1 ? '已启用' : '已停用');
        actionRef.current?.reload();
      } else {
        message.error(response.Message || '操作失败');
      }
    } finally {
      setStatusLoadingId(undefined);
    }
  };

  const handleDelete = async (record: API.PointCategoryItem) => {
    const response = await deletePointCategory(record.Id);
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
      const payload: API.SavePointCategoryParams = {
        Name: (values.Name || '').trim(),
        Sort: Number(values.Sort || 0),
        Status: values.Status ? 1 : 0,
      };

      setSubmitting(true);
      const response = editing
        ? await updatePointCategory(editing.Id, payload)
        : await createPointCategory(payload);

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

  const columns: ProColumns<API.PointCategoryItem>[] = [
    { title: 'ID', dataIndex: 'Id', width: 80 },
    { title: '分类名称', dataIndex: 'Name', width: 200 },
    { title: '排序', dataIndex: 'Sort', width: 100 },
    {
      title: '状态',
      dataIndex: 'Status',
      width: 120,
      render: (_, record) => (
        <Switch
          checked={record.Status === 1}
          checkedChildren="启用"
          unCheckedChildren="停用"
          loading={statusLoadingId === record.Id}
          onChange={(checked) => handleStatusChange(record, checked ? 1 : 0)}
        />
      ),
    },
    { title: '更新时间', dataIndex: 'UpdatedAt', width: 170 },
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
            title="确认删除该分类？"
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
      <ProTable<API.PointCategoryItem>
        headerTitle="积分商品分类"
        actionRef={actionRef}
        rowKey="Id"
        scroll={{ x: 800 }}
        search={false}
        toolBarRender={() => [
          <Button
            key="create"
            type="primary"
            icon={<PlusOutlined />}
            onClick={openCreate}
          >
            新增分类
          </Button>,
        ]}
        request={async () => {
          const response = await queryPointCategories();
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
        pagination={false}
      />

      <Drawer
        title={editing ? `编辑分类 #${editing.Id}` : '新增分类'}
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
            label="分类名称"
            name="Name"
            rules={[
              { required: true, message: '请输入分类名称' },
              { max: 60, message: '最多 60 字' },
            ]}
          >
            <Input maxLength={60} placeholder="如：周边好物" />
          </Form.Item>

          <Form.Item label="排序" name="Sort" tooltip="越小越靠前">
            <InputNumber
              min={0}
              precision={0}
              style={{ width: '100%' }}
              placeholder="0"
            />
          </Form.Item>

          <Form.Item label="启用" name="Status" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Drawer>
    </PageContainer>
  );
};

export default PointCategoriesPage;
