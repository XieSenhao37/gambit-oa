import {
  getMonthCardConfig,
  updateMonthCardConfig,
} from '@/services/monthCard';
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Space,
  message,
} from 'antd';
import { useEffect, useState } from 'react';
import { metricLabel } from './MetricHelp';

export default function CardPricing() {
  const [price, setPrice] = useState<number>(),
    [open, setOpen] = useState(false),
    [saving, setSaving] = useState(false);
  const [form] = Form.useForm();
  useEffect(() => {
    getMonthCardConfig()
      .then((r) => {
        if (r.Data) setPrice(r.Data.Price);
      })
      .catch(() => message.error('月卡价格读取失败'));
  }, []);
  return (
    <Card title={metricLabel('月卡价格')} style={{ marginBottom: 24 }}>
      <Space direction="vertical">
        <strong>
          {price === null || price === undefined
            ? '价格读取中…'
            : `¥${(price / 100).toFixed(2)} / 30 天`}
        </strong>
        <span>
          月卡仅支持玩家在小程序付费开通。订单保留开卡时的配置价格，后续调价不影响已有订单。
        </span>
        <Button
          disabled={price === null || price === undefined}
          onClick={() => {
            form.setFieldsValue({ Price: price! / 100, Note: '' });
            setOpen(true);
          }}
        >
          调整新开卡价格
        </Button>
      </Space>
      <Modal
        title="调整月卡价格"
        open={open}
        confirmLoading={saving}
        onCancel={() => setOpen(false)}
        onOk={async () => {
          const v = await form.validateFields();
          setSaving(true);
          try {
            const next = Math.round(v.Price * 100);
            await updateMonthCardConfig({
              Price: next,
              ExpectedPrice: price!,
              Note: v.Note,
            });
            setPrice(next);
            setOpen(false);
            message.success('已更新，之后的新订单使用新价格');
          } finally {
            setSaving(false);
          }
        }}
      >
        <Alert
          showIcon
          message="只影响之后的新订单，已有订单及结算池金额不变。"
        />
        <Form form={form} layout="vertical">
          <Form.Item
            name="Price"
            label="每 30 天价格（元）"
            rules={[{ required: true }]}
          >
            <InputNumber min={0.01} max={10000} precision={2} />
          </Form.Item>
          <Form.Item
            name="Note"
            label="调整说明"
            rules={[{ required: true, whitespace: true }]}
          >
            <Input.TextArea maxLength={500} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
