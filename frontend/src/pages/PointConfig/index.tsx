import { getPointConfig, updatePointConfig } from '@/services/point';
import { PageContainer } from '@ant-design/pro-components';
import {
  Alert,
  Button,
  Card,
  Form,
  InputNumber,
  message,
  Space,
  Spin,
} from 'antd';
import { useEffect, useState } from 'react';

const PointConfigPage: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState<API.PointConfig>({
    EarnThresholdAmount: 1000,
    EarnPoints: 1,
    MaxWithdrawPerTime: 0,
  });

  const loadConfig = async () => {
    setLoading(true);
    try {
      const response = await getPointConfig();
      if (response.Code === 0 && response.Data) {
        const data = response.Data;
        form.setFieldsValue({
          EarnThresholdAmountYuan: data.EarnThresholdAmount / 100,
          EarnPoints: data.EarnPoints,
          MaxWithdrawPerTime: data.MaxWithdrawPerTime,
        });
        setPreview(data);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConfig();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refreshPreview = () => {
    const values = form.getFieldsValue();
    setPreview({
      EarnThresholdAmount: Math.round(
        Number(values.EarnThresholdAmountYuan || 0) * 100,
      ),
      EarnPoints: Number(values.EarnPoints || 0),
      MaxWithdrawPerTime: Number(values.MaxWithdrawPerTime || 0),
    });
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload: API.PointConfig = {
        EarnThresholdAmount: Math.round(
          Number(values.EarnThresholdAmountYuan) * 100,
        ),
        EarnPoints: Number(values.EarnPoints),
        MaxWithdrawPerTime: Number(values.MaxWithdrawPerTime || 0),
      };
      setSaving(true);
      const response = await updatePointConfig(payload);
      if (response.Code === 0) {
        message.success('保存成功');
        setPreview(payload);
      } else {
        message.error(response.Message || '保存失败');
      }
    } catch (error: any) {
      if (error?.errorFields) {
        return;
      }
      message.error(error?.message || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <PageContainer>
      <Card title="消费得积分规则">
        <Spin spinning={loading}>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 24 }}
            message={`当前规则：每消费满 ¥${(
              preview.EarnThresholdAmount / 100
            ).toFixed(2)} 获得 ${preview.EarnPoints} 积分；${
              preview.MaxWithdrawPerTime > 0
                ? `单次提取上限 ${preview.MaxWithdrawPerTime} 积分`
                : '提取不限额'
            }`}
            description="仅游玩、餐饮订单按实付金额计分，向下取整；充值与月卡购买不计分。"
          />
          <Form
            form={form}
            layout="vertical"
            style={{ maxWidth: 420 }}
            onValuesChange={refreshPreview}
          >
            <Form.Item
              label="消费门槛（元）"
              name="EarnThresholdAmountYuan"
              rules={[{ required: true, message: '请输入消费门槛' }]}
              tooltip="每消费满该金额获得对应积分"
            >
              <InputNumber
                min={0.01}
                precision={2}
                step={1}
                style={{ width: '100%' }}
                addonBefore="¥"
              />
            </Form.Item>

            <Form.Item
              label="获得积分"
              name="EarnPoints"
              rules={[{ required: true, message: '请输入获得积分' }]}
              tooltip="每满一个门槛获得的积分数"
            >
              <InputNumber
                min={1}
                precision={0}
                step={1}
                style={{ width: '100%' }}
                addonAfter="积分"
              />
            </Form.Item>

            <Form.Item
              label="单次提取上限（积分）"
              name="MaxWithdrawPerTime"
              tooltip="0 表示不限额"
            >
              <InputNumber
                min={0}
                precision={0}
                step={10}
                style={{ width: '100%' }}
                addonAfter="积分"
              />
            </Form.Item>

            <Form.Item>
              <Space>
                <Button type="primary" loading={saving} onClick={handleSubmit}>
                  保存
                </Button>
                <Button onClick={loadConfig}>重置</Button>
              </Space>
            </Form.Item>
          </Form>
        </Spin>
      </Card>
    </PageContainer>
  );
};

export default PointConfigPage;
