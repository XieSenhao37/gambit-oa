import { Table } from '@/components/AdaptiveTable';
import ImageField from '@/components/PromotionImageUpload';
import {
  bannerPreviewUrl,
  getBanners,
  normalizeBannerPage,
  saveBanners,
  type BannerConfig,
  type HomeBanner,
} from '@/services/banner';
import { PlusOutlined } from '@ant-design/icons';
import { PageContainer } from '@ant-design/pro-components';
import {
  Alert,
  Button,
  Card,
  Form,
  Image,
  Input,
  InputNumber,
  message,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
} from 'antd';
import { useEffect, useRef, useState } from 'react';

const ACTIONS = { preview: '查看大图', page: '跳转页面', none: '不跳转' };

export default function Banners({ embedded = false }: { embedded?: boolean }) {
  const [config, setConfig] = useState<BannerConfig>();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<HomeBanner>();
  const [uploads, setUploads] = useState(0);
  const busy = useRef(false);
  const [form] = Form.useForm<HomeBanner>();
  const action = Form.useWatch('Action', form);
  const uploadBusy = (value: boolean) =>
    setUploads((count) => count + (value ? 1 : -1));
  const load = async () => {
    setLoading(true);
    try {
      setConfig(await getBanners());
    } catch {
      message.error('加载失败，请刷新重试');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    void load();
  }, []);
  const persist = async (items: HomeBanner[]) => {
    if (!config || busy.current) return false;
    busy.current = true;
    setSaving(true);
    try {
      setConfig(await saveBanners(items, config.Revision));
      message.success('已保存，重新进入小程序首页即可更新');
      return true;
    } catch {
      message.error('保存失败；如配置已被他人更新，请刷新后重试');
      return false;
    } finally {
      busy.current = false;
      setSaving(false);
    }
  };
  const open = (item?: HomeBanner) => {
    const record = item || {
      Id: `banner-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
      Title: '',
      Img: '',
      Preview: '',
      Action: 'preview' as const,
      Page: '',
      Sort: Math.min(
        9999,
        Math.max(0, ...(config?.Items || []).map((b) => b.Sort)) + 10,
      ),
      Enabled: true,
    };
    form.resetFields();
    form.setFieldsValue(record);
    setEditing(record);
  };
  const submit = async () => {
    if (!editing || uploads || busy.current) return;
    try {
      const values = await form.validateFields();
      const item = {
        ...editing,
        ...values,
        Page: values.Action === 'page' ? normalizeBannerPage(values.Page) : '',
      };
      const items = [...(config?.Items || [])];
      const index = items.findIndex((row) => row.Id === item.Id);
      if (index < 0) items.push(item);
      else items[index] = item;
      if (await persist(items)) setEditing(undefined);
    } catch {
      /* 表单内显示校验信息 */
    }
  };
  const content = (
    <>
      {!config?.Migrated && config && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="已读取现有 Banner，保存后由 OA 统一管理。"
        />
      )}
      <Card
        title="首页轮播"
        extra={
          <Space>
            <Button disabled={saving} onClick={load}>
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              disabled={
                !config || saving || loading || config.Items.length >= 30
              }
              onClick={() => open()}
            >
              新增 Banner
            </Button>
          </Space>
        }
      >
        <Table<HomeBanner>
          rowKey="Id"
          loading={loading}
          dataSource={config?.Items}
          pagination={false}
          scroll={{ x: 900 }}
          columns={[
            {
              title: '排序',
              dataIndex: 'Sort',
              width: 80,
              sorter: (a, b) => a.Sort - b.Sort,
            },
            {
              title: '展示图',
              dataIndex: 'Img',
              width: 190,
              render: (url) => (
                <Image
                  width={168}
                  height={72}
                  src={bannerPreviewUrl(url)}
                  style={{
                    objectFit: 'contain',
                    background: '#f5f6f8',
                    borderRadius: 6,
                  }}
                />
              ),
            },
            { title: '名称', dataIndex: 'Title', width: 170 },
            {
              title: '点击后',
              key: 'action',
              width: 180,
              render: (_, row) => (
                <Space direction="vertical" size={4}>
                  <Tag>{ACTIONS[row.Action]}</Tag>
                  {row.Action === 'preview' ? (
                    <Image
                      width={48}
                      height={48}
                      src={bannerPreviewUrl(row.Preview)}
                      style={{ objectFit: 'contain' }}
                    />
                  ) : row.Action === 'page' ? (
                    <Typography.Text
                      type="secondary"
                      style={{ wordBreak: 'break-all' }}
                    >
                      {row.Page}
                    </Typography.Text>
                  ) : null}
                </Space>
              ),
            },
            {
              title: '上架',
              dataIndex: 'Enabled',
              width: 85,
              render: (_, row) => (
                <Switch
                  checked={row.Enabled}
                  disabled={saving || loading}
                  onChange={(value) =>
                    persist(
                      config!.Items.map((b) =>
                        b.Id === row.Id ? { ...b, Enabled: value } : b,
                      ),
                    )
                  }
                />
              ),
            },
            {
              title: '操作',
              width: 130,
              render: (_, row) => (
                <Space>
                  <Button
                    type="link"
                    disabled={saving || loading}
                    onClick={() => open(row)}
                  >
                    编辑
                  </Button>
                  <Popconfirm
                    title="删除这条 Banner？"
                    onConfirm={() =>
                      persist(config!.Items.filter((b) => b.Id !== row.Id))
                    }
                  >
                    <Button type="link" danger disabled={saving || loading}>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Card>
      <Modal
        title={
          config?.Items.some((row) => row.Id === editing?.Id)
            ? '编辑 Banner'
            : '新增 Banner'
        }
        open={!!editing}
        width={760}
        onCancel={() => setEditing(undefined)}
        onOk={submit}
        confirmLoading={saving}
        okText="保存"
        cancelText="取消"
        okButtonProps={{ disabled: uploads > 0 }}
        cancelButtonProps={{ disabled: saving || uploads > 0 }}
        closable={!saving && uploads === 0}
        maskClosable={false}
        keyboard={!saving && uploads === 0}
      >
        <Form
          form={form}
          layout="vertical"
          style={{ marginTop: 24 }}
          disabled={saving}
        >
          <Form.Item
            name="Title"
            label="名称"
            rules={[
              { required: true, whitespace: true, message: '请输入名称' },
            ]}
          >
            <Input maxLength={60} placeholder="仅用于后台识别，如：门店价格" />
          </Form.Item>
          <Form.Item
            name="Img"
            label="首页展示图"
            rules={[{ required: true, message: '请上传首页展示图' }]}
          >
            <ImageField wide onBusy={uploadBusy} />
          </Form.Item>
          <Form.Item
            name="Action"
            label="点击方式"
            rules={[{ required: true }]}
          >
            <Select
              disabled={saving || uploads > 0}
              options={Object.entries(ACTIONS).map(([value, label]) => ({
                value,
                label,
              }))}
            />
          </Form.Item>
          {action === 'preview' && (
            <Form.Item
              name="Preview"
              label="点击后展示的大图"
              rules={[{ required: true, message: '请上传点击后展示的大图' }]}
            >
              <ImageField onBusy={uploadBusy} />
            </Form.Item>
          )}
          {action === 'page' && (
            <Form.Item
              name="Page"
              label="小程序页面路径"
              rules={[
                {
                  required: true,
                  whitespace: true,
                  message: '请输入小程序页面路径',
                },
                {
                  validator: (_, value) =>
                    !value || normalizeBannerPage(value)
                      ? Promise.resolve()
                      : Promise.reject(
                          new Error(
                            '请输入有效的页面路径，如 /pages/eventCalendar/index',
                          ),
                        ),
                },
              ]}
            >
              <Input
                maxLength={2048}
                placeholder="/pages/eventCalendar/index（支持 ?key=value 参数）"
              />
            </Form.Item>
          )}
          <Space size={40} align="start">
            <Form.Item
              name="Sort"
              label="排序（数字越小越靠前）"
              rules={[{ required: true }]}
            >
              <InputNumber min={0} max={9999} precision={0} />
            </Form.Item>
            <Form.Item name="Enabled" label="上架" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </>
  );
  return embedded ? (
    content
  ) : (
    <PageContainer title="首页 Banner">{content}</PageContainer>
  );
}
