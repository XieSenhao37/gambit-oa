import { call, Policy } from "@/services/gameServices";
import { PageContainer } from "@ant-design/pro-components";
import {
  Button,
  Card,
  Checkbox,
  Col,
  Divider,
  Form,
  Input,
  InputNumber,
  message,
  Row,
  Space,
  Spin,
  Switch,
} from "antd";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { history } from "@umijs/max";
const required = [{ required: true, message: "请填写" }];
export default function GameServices() {
  const [policyForm] = Form.useForm();
  const [policy, setPolicy] = useState<{ Policy: Policy; Revision: number }>();
  const [loading, setLoading] = useState(true),
    [saving, setSaving] = useState(false);
  async function load() {
    setLoading(true);
    try {
      const p = await call<{ Policy: Policy; Revision: number }>("policy");
      setPolicy(p);
      policyForm.setFieldsValue(p.Policy);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  async function savePolicy(values: Policy) {
    setSaving(true);
    try {
      await call("policy", "PUT", {
        Policy: {
          ...policy?.Policy,
          ...values,
          Discounts: values.Discounts || [],
        },
        Revision: policy?.Revision,
      });
      message.success("门店租售设置已更新");
      await load();
    } finally {
      setSaving(false);
    }
  }
  return (
    <PageContainer
      title="门店租售设置"
      extra={
        <Button onClick={() => history.push("/games")}>返回桌游库存</Button>
      }
    >
      <Spin spinning={loading}>
        <Card>
          <Form
            form={policyForm}
            layout="vertical"
            onFinish={savePolicy}
            style={{ maxWidth: 960 }}
          >
            <Row gutter={24}>
              {[
                ["RentalEnabled", "开启桌游租赁"],
                ["PurchaseEnabled", "开启桌游出售"],
                ["Pickup", "支持门店自提"],
                ["Shipping", "支持顺丰到付"],
              ].map(([name, label]) => (
                <Col xs={12} md={6} key={name}>
                  <Form.Item name={name} label={label} valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </Col>
              ))}
            </Row>
            <Form.Item noStyle shouldUpdate={(prev, next) => prev.Shipping !== next.Shipping}>
              {({ getFieldValue }) => getFieldValue("Shipping") && <Form.Item name="ShippingServices" label="顺丰配送档位" rules={[{ required: true, type: "array", min: 1, message: "请选择至少一种配送档位" }]} extra="租赁和购买共用；运费到付，同城范围及运费需门店确认。">
                <Checkbox.Group options={[{ label: "普快", value: "sf_standard" }, { label: "特快", value: "sf_express" }, { label: "同城秒送", value: "sf_local" }]} />
              </Form.Item>}
            </Form.Item>
            <Row gutter={24}>
              {[
                ["MinDays", "最短租期（天）", 1, 365],
                ["MaxDays", "最长租期（天）", 1, 365],
                ["MaxQuantity", "单笔总数量上限", 1, 100],
                ["AdvanceDays", "可提前预约天数", 0, 365],
              ].map(([name, label, min, max]) => (
                <Col xs={12} md={6} key={String(name)}>
                  <Form.Item name={name} label={label} rules={required}>
                    <InputNumber
                      min={Number(min)}
                      max={Number(max)}
                      precision={0}
                      style={{ width: "100%" }}
                    />
                  </Form.Item>
                </Col>
              ))}
            </Row>
            <Form.List name="Discounts">
              {(fields, { add, remove }) => (
                <>
                  <strong>长租折扣阶梯</strong>
                  <div style={{ margin: "16px 0" }}>
                    {fields.map((f) => (
                      <Space key={f.key} align="start">
                        <Form.Item name={[f.name, "MinDays"]} rules={required}>
                          <InputNumber
                            min={1}
                            max={365}
                            addonBefore="满"
                            addonAfter="天"
                            precision={0}
                          />
                        </Form.Item>
                        <Form.Item name={[f.name, "Percent"]} rules={required}>
                          <InputNumber
                            min={1}
                            max={100}
                            addonAfter="%"
                            precision={0}
                          />
                        </Form.Item>
                        <Button
                          icon={<DeleteOutlined />}
                          onClick={() => remove(f.name)}
                        />
                      </Space>
                    ))}
                  </div>
                  <Button
                    onClick={() => add({ MinDays: 3, Percent: 80 })}
                    icon={<PlusOutlined />}
                  >
                    添加阶梯
                  </Button>
                  <p style={{ color: "#888" }}>
                    按符合条件的最优惠折扣计算；80% 为八折。押金不参与折扣。
                  </p>
                </>
              )}
            </Form.List>
            <Divider orientation="left">邮寄归还收件信息</Divider>
            <p style={{ color: '#667080', marginBottom: 20 }}>玩家选择“邮寄还”时展示，支持一键复制。请填写实际收件地址。</p>
            <Row gutter={24}>
              <Col xs={24} md={12}><Form.Item name="ReturnRecipient" label="收件人"><Input maxLength={60} placeholder="收件人姓名" /></Form.Item></Col>
              <Col xs={24} md={12}><Form.Item name="ReturnPhone" label="联系电话"><Input maxLength={40} placeholder="收件联系电话" /></Form.Item></Col>
            </Row>
            <Form.Item name="ReturnAddress" label="详细收件地址" extra="三项完整填写后可用；全部清空则不提供邮寄归还地址。"><Input.TextArea rows={2} maxLength={300} placeholder="省市区、街道及门牌号" /></Form.Item>
            <Divider />
            <Form.Item name="RentalTerms" label="租赁规则（结算时展示）">
              <Input.TextArea rows={4} maxLength={3000} showCount />
            </Form.Item>
            <Form.Item
              name="PurchaseTerms"
              label="购买与售后规则（结算时展示）"
            >
              <Input.TextArea rows={4} maxLength={3000} showCount />
            </Form.Item>
            <Button htmlType="submit" type="primary" loading={saving}>
              保存当前门店规则
            </Button>
          </Form>
        </Card>
      </Spin>
    </PageContainer>
  );
}
