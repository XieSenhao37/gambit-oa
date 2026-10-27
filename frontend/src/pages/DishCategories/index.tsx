import { ProTable } from '@/components/AdaptiveTable';
import {
  deleteDishCategory,
  queryDishCategories,
  saveDishCategory,
} from '@/services/dish';
import { PlusOutlined } from '@ant-design/icons';
import {
  PageContainer,
  type ActionType,
  type ProColumns,
} from '@ant-design/pro-components';
import {
  Alert,
  Button,
  Drawer,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Popconfirm,
  Space,
} from 'antd';
import { useRef, useState } from 'react';

const DishCategoriesPage: React.FC = () => {
  const actionRef = useRef<ActionType>();
  const [form] = Form.useForm();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<API.DishCategory>();
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number>();
  const savingRef = useRef(false);

  const edit = (item?: API.DishCategory) => {
    setEditing(item);
    form.resetFields();
    form.setFieldsValue({ Name: item?.Name || '', Sort: item?.Sort ?? 0 });
    setOpen(true);
  };
  const close = () => {
    if (saving) return;
    const dismiss = () => setOpen(false);
    const values = form.getFieldsValue();
    if (
      values.Name !== (editing?.Name || '') ||
      values.Sort !== (editing?.Sort ?? 0)
    ) {
      Modal.confirm({
        className: 'oa-operation-modal',
        title: '放弃未保存的修改？',
        okText: '放弃修改',
        cancelText: '继续编辑',
        onOk: dismiss,
      });
    } else dismiss();
  };
  const save = async () => {
    if (savingRef.current) return;
    savingRef.current = true;
    try {
      const values = await form.validateFields();
      setSaving(true);
      const response = await saveDishCategory(
        {
          Name: values.Name.trim(),
          Sort: values.Sort ?? 0,
          Revision: editing?.Revision,
        },
        editing?.Id,
      );
      if (response.Code !== 0) {
        message.error(response.Message || '保存失败');
        return;
      }
      message.success(editing ? '分类已更新' : '分类已创建');
      setOpen(false);
      actionRef.current?.reload();
    } catch (error: any) {
      if (!error?.errorFields) actionRef.current?.reload();
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };
  const remove = async (item: API.DishCategory) => {
    setDeletingId(item.Id);
    try {
      const response = await deleteDishCategory(item);
      if (response.Code === 0) {
        message.success('分类已删除');
        actionRef.current?.reload();
      } else message.error(response.Message || '删除失败');
    } catch {
      actionRef.current?.reload();
    } finally {
      setDeletingId(undefined);
    }
  };
  const columns: ProColumns<API.DishCategory>[] = [
    { title: '分类名称', dataIndex: 'Name', ellipsis: true, width: 320 },
    { title: '排序', dataIndex: 'Sort', width: 120 },
    {
      title: '操作',
      key: 'action',
      width: 160,
      fixed: 'right',
      render: (_, item) => (
        <Space>
          <Button
            type="link"
            disabled={!!deletingId}
            onClick={() => edit(item)}
          >
            编辑
          </Button>
          <Popconfirm
            title={`删除“${item.Name}”？`}
            description="被餐品引用的分类不能删除。"
            onConfirm={() => remove(item)}
            okText="删除"
            cancelText="取消"
            disabled={!!deletingId}
          >
            <Button
              type="link"
              danger
              loading={deletingId === item.Id}
              disabled={!!deletingId && deletingId !== item.Id}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <PageContainer>
      <Alert
        type="info"
        showIcon
        message="分类由所有门店共用，排序数值越小越靠前。"
        style={{ marginBottom: 16 }}
      />
      <ProTable<API.DishCategory>
        headerTitle="餐品分类"
        actionRef={actionRef}
        rowKey="Id"
        columns={columns}
        search={false}
        pagination={false}
        locale={{ emptyText: '暂无餐品分类，请先新增分类' }}
        toolBarRender={() => [
          <Button
            key="create"
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => edit()}
          >
            新增分类
          </Button>,
        ]}
        request={async () => {
          const response = await queryDishCategories();
          return {
            data: response.Data?.Items || [],
            success: response.Code === 0,
          };
        }}
      />
      <Drawer
        rootClassName="oa-operation-modal"
        title={editing ? '编辑餐品分类' : '新增餐品分类'}
        width={460}
        open={open}
        onClose={close}
        closable={!saving}
        maskClosable={!saving}
        keyboard={!saving}
        destroyOnClose
        extra={
          <Space>
            <Button onClick={close} disabled={saving}>
              取消
            </Button>
            <Button type="primary" loading={saving} onClick={save}>
              保存
            </Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical" disabled={saving}>
          <Form.Item
            label="分类名称"
            name="Name"
            validateTrigger="onBlur"
            rules={[
              { required: true, whitespace: true, message: '请输入分类名称' },
              { max: 60, message: '最多 60 字' },
            ]}
          >
            <Input maxLength={60} placeholder="如：咖啡、茶饮、小食" />
          </Form.Item>
          <Form.Item
            label="排序"
            name="Sort"
            extra="数值越小越靠前，相同时按分类创建顺序排列。"
            rules={[{ required: true, message: '请输入排序' }]}
          >
            <InputNumber
              min={0}
              max={2147483647}
              precision={0}
              style={{ width: '100%' }}
            />
          </Form.Item>
        </Form>
      </Drawer>
    </PageContainer>
  );
};

export default DishCategoriesPage;
