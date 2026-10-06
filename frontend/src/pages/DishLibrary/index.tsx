import { ProTable } from '@/components/AdaptiveTable';
import {
  createDishLibraryItem,
  deleteDishLibraryItem,
  queryDishLibrary,
  updateDishLibraryItem,
} from '@/services/dish';
import { cosThumb } from '@/utils/cosImage';
import { PlusOutlined, UploadOutlined } from '@ant-design/icons';
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
  Input,
  InputNumber,
  message,
  Popconfirm,
  Select,
  Space,
  Tag,
  Upload,
  type UploadFile,
} from 'antd';
import { useRef, useState } from 'react';

const formatPrice = (cents?: number) => ((cents || 0) / 100).toFixed(2);

const DishLibraryPage: React.FC = () => {
  const actionRef = useRef<ActionType>();
  const [form] = Form.useForm();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<API.DishLibraryItem | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [categories, setCategories] = useState<API.DishCategory[]>([]);
  const [options, setOptions] = useState<API.DishOption[]>([]);

  const openCreate = () => {
    setEditing(null);
    setFileList([]);
    form.resetFields();
    form.setFieldsValue({
      DefaultPrice: 0,
      CategoryIds: [],
      Options: [],
      Tags: [],
    });
    setDrawerOpen(true);
  };

  const openEdit = (record: API.DishLibraryItem) => {
    setEditing(record);
    setFileList(
      record.ImageUrl
        ? [
            {
              uid: 'existing',
              name: '餐品图片',
              status: 'done',
              url: cosThumb(record.ImageUrl, 'sm'),
              thumbUrl: cosThumb(record.ImageUrl, 'sm'),
            } as UploadFile,
          ]
        : [],
    );
    form.setFieldsValue({
      Name: record.Name,
      DefaultPrice: record.DefaultPrice / 100,
      CategoryIds: record.CategoryIds,
      Options: record.Options,
      Description: record.Description,
      Tags: record.Tags,
    });
    setDrawerOpen(true);
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
    setEditing(null);
    setFileList([]);
    form.resetFields();
  };

  const buildFormData = (values: any) => {
    const formData = new FormData();
    formData.append('Name', values.Name?.trim());
    formData.append('DefaultPrice', String(Number(values.DefaultPrice || 0)));
    formData.append('CategoryIds', JSON.stringify(values.CategoryIds || []));
    formData.append('Options', JSON.stringify(values.Options || []));
    formData.append('Description', values.Description || '');
    formData.append('Tags', JSON.stringify(values.Tags || []));
    const imageFile = fileList.find((file) => file.originFileObj);
    if (imageFile?.originFileObj) {
      formData.append('Image', imageFile.originFileObj as Blob);
    } else if (editing?.ImageUrl) {
      formData.append('ImageUrl', editing.ImageUrl);
    }
    return formData;
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const hasImage = fileList.some((file) => file.originFileObj || file.url);
      if (!hasImage) {
        message.error('请上传餐品图片');
        return;
      }
      setSubmitting(true);
      const response = editing
        ? await updateDishLibraryItem(editing.Id, buildFormData(values))
        : await createDishLibraryItem(buildFormData(values));
      if (response.Code === 0) {
        message.success(editing ? '更新成功' : '创建成功');
        closeDrawer();
        actionRef.current?.reload();
      } else {
        message.error(response.Message || '保存失败');
      }
    } catch (error: any) {
      if (!error?.errorFields) {
        message.error(error?.message || '保存失败');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (record: API.DishLibraryItem) => {
    const response = await deleteDishLibraryItem(record.Id);
    if (response.Code === 0) {
      message.success('删除成功');
      actionRef.current?.reload();
    } else {
      message.error(response.Message || '删除失败');
    }
  };

  const renderCategoryNames = (ids: number[] = []) => {
    return ids
      .map((id) => categories.find((category) => category.Id === id)?.Name)
      .filter(Boolean) as string[];
  };

  const columns: ProColumns<API.DishLibraryItem>[] = [
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
      width: 180,
      fieldProps: { placeholder: '搜索餐品名称' },
    },
    {
      title: '默认价格',
      dataIndex: 'DefaultPrice',
      width: 120,
      search: false,
      render: (_, record) => `¥${formatPrice(record.DefaultPrice)}`,
    },
    {
      title: '分类',
      dataIndex: 'CategoryIds',
      width: 180,
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
      title: '标签',
      dataIndex: 'Tags',
      width: 180,
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
      title: '描述',
      dataIndex: 'Description',
      ellipsis: true,
      search: false,
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
            title="确认删除该餐品信息？"
            description="已被门店菜单引用的餐品不能删除。"
            onConfirm={() => handleDelete(record)}
            okText="确认"
            cancelText="取消"
          >
            <Button danger type="link">
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <PageContainer>
      <ProTable<API.DishLibraryItem>
        headerTitle="餐品信息库"
        actionRef={actionRef}
        rowKey="Id"
        scroll={{ x: 1100 }}
        search={{ labelWidth: 'auto', defaultCollapsed: false }}
        toolBarRender={() => [
          <Button
            key="create"
            type="primary"
            icon={<PlusOutlined />}
            onClick={openCreate}
          >
            新增餐品
          </Button>,
        ]}
        request={async (params) => {
          const response = await queryDishLibrary({
            current: params.current,
            pageSize: params.pageSize,
            Keyword: params.Name,
          });
          if (response.Code === 0 && response.Data) {
            setCategories(response.Data.Categories || []);
            setOptions(response.Data.Options || []);
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
        title={editing ? `编辑餐品 #${editing.Id}` : '新增餐品'}
        width={520}
        open={drawerOpen}
        onClose={closeDrawer}
        destroyOnClose
        extra={
          <Space>
            <Button onClick={closeDrawer}>取消</Button>
            <Button type="primary" loading={submitting} onClick={handleSubmit}>
              保存
            </Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item label="餐品图片" required>
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
            label="餐品名称"
            name="Name"
            rules={[
              { required: true, message: '请输入餐品名称' },
              { max: 60, message: '最多 60 字' },
            ]}
          >
            <Input placeholder="如：拿铁咖啡" />
          </Form.Item>

          <Form.Item
            label="默认价格（元）"
            name="DefaultPrice"
            rules={[{ required: true, message: '请输入默认价格' }]}
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

          <Form.Item
            label="分类"
            name="CategoryIds"
            rules={[{ required: true, message: '请选择分类' }]}
          >
            <Select
              mode="multiple"
              placeholder="选择分类"
              options={categories.map((category) => ({
                label: category.Name,
                value: category.Id,
              }))}
            />
          </Form.Item>

          <Form.Item label="选项" name="Options" tooltip="如规格、温度、糖度等">
            <Select
              mode="multiple"
              placeholder="选择可用选项（可多选）"
              optionLabelProp="label"
              options={options.map((option) => {
                const itemNames = (option.Items || [])
                  .map((item) => item?.Name)
                  .filter(Boolean)
                  .join(' / ');
                const suffix = itemNames ? `（${itemNames}）` : '';
                return {
                  label: `${option.Name}${suffix}`,
                  value: option.Id,
                };
              })}
              allowClear
            />
          </Form.Item>

          <Form.Item label="标签" name="Tags" tooltip="自定义标签，回车确认">
            <Select
              mode="tags"
              placeholder="如：新品、热销"
              tokenSeparators={[',']}
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

export default DishLibraryPage;
