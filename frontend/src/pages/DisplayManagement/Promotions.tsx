import brandLogo from '@/assets/promotion-brand.png';
import { Table } from '@/components/AdaptiveTable';
import ImageField from '@/components/PromotionImageUpload';
import { bannerPreviewUrl } from '@/services/banner';
import {
  getPromotions,
  savePromotions,
  type HomePromotions,
  type PopupImage,
  type PromotionResponse,
} from '@/services/promotion';
import { PlusOutlined } from '@ant-design/icons';
import {
  Button,
  Card,
  Form,
  Image,
  Input,
  InputNumber,
  message,
  Modal,
  Popconfirm,
  Radio,
  Space,
  Switch,
  Typography,
} from 'antd';
import { useEffect, useRef, useState } from 'react';

const FREQUENCIES = [
  { label: '每天一次', value: 'daily' },
  { label: '每次进入', value: 'entry' },
];
export default function Promotions({ kind }: { kind: 'splash' | 'popup' }) {
  const [previewHeight, setPreviewHeight] = useState(460);
  const posterWidth = Math.min(230, ((previewHeight - 32 - 116) * 3) / 4);
  const [data, setData] = useState<PromotionResponse>();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [editing, setEditing] = useState<PopupImage>();
  const busy = useRef(false);
  const [splashForm] = Form.useForm<HomePromotions['Splash']>();
  const [popupForm] = Form.useForm<PopupImage>();
  const previewImg = Form.useWatch('Img', splashForm);
  const seconds = Form.useWatch('Seconds', splashForm);
  const load = async () => {
    setLoading(true);
    try {
      const result = await getPromotions();
      setData(result);
      splashForm.setFieldsValue(result.Config.Splash);
    } catch {
      message.error('加载失败，请刷新重试');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    void load();
  }, []);
  const persist = async (config: HomePromotions) => {
    if (!data || busy.current) return false;
    busy.current = true;
    setSaving(true);
    try {
      const result = await savePromotions(config, data.Revision);
      setData(result);
      message.success('已保存，下次符合条件进入首页时生效');
      return true;
    } catch {
      message.error('保存失败，如配置已被他人修改，请刷新后重试');
      return false;
    } finally {
      busy.current = false;
      setSaving(false);
    }
  };
  const saveSplash = async () => {
    if (!data || uploading) return;
    try {
      const Splash = await splashForm.validateFields();
      await persist({ ...data.Config, Splash });
    } catch {
      /* 表单提示校验错误 */
    }
  };
  const openPopup = (item?: PopupImage) => {
    const value = item || {
      Id: `popup-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      Title: '',
      Img: '',
      Enabled: true,
      Sort: Math.min(
        9999,
        Math.max(0, ...(data?.Config.Popup.Items || []).map((b) => b.Sort)) +
          10,
      ),
    };
    popupForm.resetFields();
    popupForm.setFieldsValue(value);
    setEditing(value);
  };
  const savePopup = async () => {
    if (!data || !editing || uploading) return;
    try {
      const item = { ...editing, ...(await popupForm.validateFields()) };
      const items = [...data.Config.Popup.Items];
      const index = items.findIndex((b) => b.Id === item.Id);
      if (index < 0) items.push(item);
      else items[index] = item;
      if (
        await persist({
          ...data.Config,
          Popup: { ...data.Config.Popup, Items: items },
        })
      )
        setEditing(undefined);
    } catch {
      /* 表单提示校验错误 */
    }
  };
  return (
    <>
      <Card
        title={kind === 'splash' ? '开屏展示' : '首页弹窗'}
        loading={loading}
        extra={
          <Button disabled={saving || uploading} onClick={load}>
            刷新
          </Button>
        }
      >
        {data && kind === 'splash' && (
          <div style={{ display: 'flex', gap: 48, flexWrap: 'wrap' }}>
            <Form
              form={splashForm}
              layout="vertical"
              style={{ flex: '1 1 320px', maxWidth: 520 }}
              disabled={saving}
            >
              <Form.Item
                name="Title"
                label="名称"
                rules={[{ required: true, whitespace: true }]}
              >
                <Input maxLength={60} />
              </Form.Item>
              <Form.Item
                name="Img"
                label="开屏图片"
                dependencies={['Enabled']}
                rules={[
                  ({ getFieldValue }) => ({
                    validator: (_, value) =>
                      getFieldValue('Enabled') && !value
                        ? Promise.reject(new Error('请上传图片后再上线'))
                        : Promise.resolve(),
                  }),
                ]}
              >
                <ImageField
                  variant="splash"
                  onBusy={setUploading}
                  disabled={saving}
                />
              </Form.Item>
              <Form.Item name="Frequency" label="展示频率">
                <Radio.Group options={FREQUENCIES} />
              </Form.Item>
              <Form.Item
                name="Seconds"
                label="展示时长"
                rules={[{ required: true }]}
              >
                <InputNumber min={2} max={5} precision={0} addonAfter="秒" />
              </Form.Item>
              <Form.Item name="Enabled" label="上线" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Button
                type="primary"
                loading={saving}
                disabled={uploading}
                onClick={saveSplash}
              >
                保存配置
              </Button>
            </Form>
            <div>
              <Typography.Paragraph type="secondary">
                全屏预览
              </Typography.Paragraph>
              <div
                style={{
                  width: 230,
                  height: previewHeight,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  paddingTop: 32,
                  boxSizing: 'content-box',
                  border: '6px solid #202124',
                  borderRadius: 28,
                  overflow: 'hidden',
                  position: 'relative',
                  background: '#fff',
                }}
              >
                {previewImg && (
                  <img
                    src={bannerPreviewUrl(previewImg)}
                    style={{
                      width: posterWidth,
                      height: (posterWidth * 4) / 3,
                      flexShrink: 0,
                      objectFit: 'contain',
                      background: '#f5f5f5',
                    }}
                  />
                )}
                <div
                  style={{
                    flex: 1,
                    minHeight: 116,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    paddingBottom: 42,
                    boxSizing: 'border-box',
                  }}
                >
                  <img
                    src={brandLogo}
                    style={{ width: 80, height: 47, objectFit: 'cover' }}
                  />
                  <span
                    style={{
                      fontSize: 4.9,
                      whiteSpace: 'nowrap',
                      marginTop: 5,
                    }}
                  >
                    Board Games 桌游 / TCG 集换式卡牌 / Collectable Cards 收藏卡
                  </span>
                  <span style={{ fontSize: 7, color: '#777', marginTop: 3 }}>
                    It All Starts At The Table
                  </span>
                </div>
                <div
                  style={{
                    position: 'absolute',
                    top: 12,
                    right: 12,
                    borderRadius: 20,
                    background: '#ffffffcc',
                    padding: '2px 12px',
                  }}
                >
                  •••　◉
                </div>
                <span
                  style={{
                    position: 'absolute',
                    right: 16,
                    bottom: 12,
                    background: '#0007',
                    borderRadius: 20,
                    padding: '4px 12px',
                    color: '#fff',
                  }}
                >
                  跳过 {seconds || 3}s
                </span>
              </div>
              <Typography.Paragraph
                type="secondary"
                style={{ width: 242, marginTop: 12 }}
              >
                3:4
                海报完整展示，底部品牌区随屏幕高度变化；短屏等比缩小海报。始终可跳过。
                <Radio.Group
                  size="small"
                  value={previewHeight}
                  onChange={(e) => setPreviewHeight(e.target.value)}
                  options={[
                    { label: '短屏', value: 380 },
                    { label: '标准屏', value: 460 },
                    { label: '长屏', value: 510 },
                  ]}
                />
              </Typography.Paragraph>
            </div>
          </div>
        )}
        {data && kind === 'popup' && (
          <>
            <Space size={32} wrap style={{ marginBottom: 24 }}>
              <Space>
                整体上线
                <Switch
                  checked={data.Config.Popup.Enabled}
                  disabled={saving}
                  onChange={(Enabled) =>
                    persist({
                      ...data.Config,
                      Popup: { ...data.Config.Popup, Enabled },
                    })
                  }
                />
              </Space>
              <Space>
                展示频率
                <Radio.Group
                  options={FREQUENCIES}
                  value={data.Config.Popup.Frequency}
                  disabled={saving}
                  onChange={(e) =>
                    persist({
                      ...data.Config,
                      Popup: {
                        ...data.Config.Popup,
                        Frequency: e.target.value,
                      },
                    })
                  }
                />
              </Space>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                disabled={saving || data.Config.Popup.Items.length >= 20}
                onClick={() => openPopup()}
              >
                新增图片
              </Button>
            </Space>
            <Typography.Paragraph type="secondary">
              多张上线图片在同一个弹窗中左右滑动，关闭一次即关闭整组。
            </Typography.Paragraph>
            <Table<PopupImage>
              dataSource={data.Config.Popup.Items}
              rowKey="Id"
              pagination={false}
              columns={[
                { title: '排序', dataIndex: 'Sort', width: 90 },
                {
                  title: '图片',
                  dataIndex: 'Img',
                  width: 130,
                  render: (url) => (
                    <Image
                      width={80}
                      height={107}
                      style={{ objectFit: 'contain' }}
                      src={bannerPreviewUrl(url)}
                    />
                  ),
                },
                { title: '名称', dataIndex: 'Title' },
                {
                  title: '上线',
                  render: (_, item) => (
                    <Switch
                      checked={item.Enabled}
                      disabled={saving}
                      onChange={(Enabled) =>
                        persist({
                          ...data.Config,
                          Popup: {
                            ...data.Config.Popup,
                            Items: data.Config.Popup.Items.map((b) =>
                              b.Id === item.Id ? { ...b, Enabled } : b,
                            ),
                          },
                        })
                      }
                    />
                  ),
                },
                {
                  title: '操作',
                  render: (_, item) => (
                    <Space>
                      <Button
                        type="link"
                        disabled={saving}
                        onClick={() => openPopup(item)}
                      >
                        编辑
                      </Button>
                      <Popconfirm
                        title="删除这张弹窗图片？"
                        onConfirm={() =>
                          persist({
                            ...data.Config,
                            Popup: {
                              ...data.Config.Popup,
                              Items: data.Config.Popup.Items.filter(
                                (b) => b.Id !== item.Id,
                              ),
                            },
                          })
                        }
                      >
                        <Button type="link" danger disabled={saving}>
                          删除
                        </Button>
                      </Popconfirm>
                    </Space>
                  ),
                },
              ]}
            />
          </>
        )}
      </Card>
      <Typography.Paragraph type="secondary" style={{ marginTop: 16 }}>
        每天一次按同一设备、北京时间自然日分别计次；每次进入指启动或从微信重新进入首页，站内切换页面不重复展示。
      </Typography.Paragraph>
      <Modal
        title={
          data?.Config.Popup.Items.some((b) => b.Id === editing?.Id)
            ? '编辑弹窗图片'
            : '新增弹窗图片'
        }
        open={!!editing}
        onCancel={() => setEditing(undefined)}
        onOk={savePopup}
        confirmLoading={saving}
        okText="保存"
        cancelText="取消"
        okButtonProps={{ disabled: uploading }}
        cancelButtonProps={{ disabled: saving || uploading }}
        closable={!saving && !uploading}
        keyboard={!saving && !uploading}
        maskClosable={false}
      >
        <Form
          form={popupForm}
          layout="vertical"
          disabled={saving}
          style={{ marginTop: 24 }}
        >
          <Form.Item
            name="Title"
            label="名称"
            rules={[{ required: true, whitespace: true }]}
          >
            <Input maxLength={60} placeholder="仅用于后台识别" />
          </Form.Item>
          <Form.Item
            name="Img"
            label="图片"
            rules={[{ required: true, message: '请上传图片' }]}
          >
            <ImageField
              variant="popup"
              onBusy={setUploading}
              disabled={saving}
            />
          </Form.Item>
          <Form.Item
            name="Sort"
            label="排序（数字越小越靠前）"
            rules={[{ required: true }]}
          >
            <InputNumber min={0} max={9999} precision={0} />
          </Form.Item>
          <Form.Item name="Enabled" label="上线" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
