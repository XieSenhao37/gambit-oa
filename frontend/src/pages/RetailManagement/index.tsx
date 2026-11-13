import { useEffect, useRef, useState } from 'react';
import { PageContainer } from '@ant-design/pro-components';
import {
  Alert,
  Button,
  Card,
  Checkbox,
  DatePicker,
  Drawer,
  Form,
  Input,
  InputNumber,
  message,
  Select,
  Space,
  Switch,
  Tabs,
} from 'antd';
import dayjs from 'dayjs';
import { Table } from '@/components/AdaptiveTable';
import RetailEditor, { useMutationKey } from '@/components/RetailEditor';
import {
  call,
  CouponTemplate,
  money,
  Policy,
  Product,
  SKU,
} from '@/services/retail';

const required = [{ required: true, message: '请填写' }];
function StockEditor({
  sku,
  name,
  close,
  saved,
}: {
  sku: SKU;
  name: string;
  close: () => void;
  saved: () => void;
}) {
  const [form] = Form.useForm();
  const key = useMutationKey();
  return (
    <RetailEditor
      title={`${name} · ${sku.Name}`}
      form={form}
      initialValues={{
        Price: sku.Price / 100,
        Available: sku.Available,
        Enabled: sku.OnSale,
      }}
      onClose={close}
      onSave={async (v) => {
        const data = {
          ...v,
          Price: Math.round(v.Price * 100),
          SKUID: sku.ID,
          Version: sku.Version,
        };
        await call('stock', 'PUT', { ...data, RequestKey: key(data) });
        saved();
      }}
    >
      <Form.Item name="Price" label="售价（元）" rules={required}>
        <InputNumber min={0.01} max={1000000} precision={2} />
      </Form.Item>
      <Form.Item
        name="Available"
        label="可售库存"
        rules={required}
        extra="这里调整剩余可售数量，已下单商品不会被释放。"
      >
        <InputNumber min={0} max={1000000} precision={0} />
      </Form.Item>
      <Form.Item name="Enabled" label="本店上架" valuePropName="checked">
        <Switch />
      </Form.Item>
      <Form.Item name="Reason" label="调整备注（选填）">
        <Input maxLength={500} />
      </Form.Item>
    </RetailEditor>
  );
}
function CouponEditor({
  template,
  close,
  saved,
}: {
  template: Partial<CouponTemplate>;
  close: () => void;
  saved: () => void;
}) {
  const [form] = Form.useForm();
  const [options, setOptions] = useState<{ value: number; label: string }[]>(
    []
  );
  const seq = useRef(0);
  const search = async (Keyword: string) => {
    const token = ++seq.current;
    try {
      const r = await call<{ Products: Product[] }>('products', 'GET', {
        Keyword,
        PageSize: 50,
      });
      if (seq.current === token)
        setOptions((old) =>
          Array.from(
            new Map(
              [
                ...old,
                ...r.Products.map((p) => ({ value: p.ID, label: p.Name })),
              ].map((p) => [p.value, p])
            ).values()
          )
        );
    } catch (e) {
      message.error('商品搜索失败');
    }
  };
  useEffect(() => {
    void search('');
    return () => {
      seq.current++;
    };
  }, []);
  return (
    <RetailEditor
      title={template.ID ? '编辑商城券' : '新建商城券'}
      form={form}
      initialValues={{
        Enabled: true,
        Claimable: false,
        TotalLimit: 100,
        PerUserLimit: 1,
        ...template,
        Amount: (template.Amount || 0) / 100,
        Minimum: (template.Minimum || 0) / 100,
        Dates: [
          dayjs(template.StartsAt),
          dayjs(template.EndsAt || Date.now() + 30 * 86400000),
        ],
      }}
      onClose={close}
      onSave={async (v) => {
        await call('coupon-templates', 'PUT', {
          ...v,
          ID: template.ID || 0,
          Version: template.Version || 0,
          Amount: Math.round(v.Amount * 100),
          Minimum: Math.round(v.Minimum * 100),
          StartsAt: v.Dates[0].toISOString(),
          EndsAt: v.Dates[1].toISOString(),
          ProductIDs: v.ProductIDs || [],
        });
        saved();
      }}
    >
      <Form.Item name="Name" label="券名称" rules={required}>
        <Input maxLength={100} />
      </Form.Item>
      <Space align="start">
        <Form.Item name="Amount" label="立减金额（元）" rules={required}>
          <InputNumber min={0.01} max={1000000} precision={2} />
        </Form.Item>
        <Form.Item name="Minimum" label="使用门槛（元）" rules={required}>
          <InputNumber min={0} max={1000000} precision={2} />
        </Form.Item>
      </Space>
      <Form.Item
        name="ProductIDs"
        label="适用商品"
        extra="留空表示本店商城全部商品；门槛仅计算选中商品金额。"
      >
        <Select
          mode="multiple"
          showSearch
          filterOption={false}
          onSearch={search}
          options={options}
          placeholder="搜索并选择商品"
        />
      </Form.Item>
      <Form.Item name="Dates" label="有效期" rules={required}>
        <DatePicker.RangePicker showTime />
      </Form.Item>
      <Space align="start">
        <Form.Item name="TotalLimit" label="发行总量" rules={required}>
          <InputNumber min={1} max={1000000} precision={0} />
        </Form.Item>
        <Form.Item name="PerUserLimit" label="每人限领" rules={required}>
          <InputNumber min={1} max={100} precision={0} />
        </Form.Item>
        <Form.Item name="Enabled" label="启用发放" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item
          name="Claimable"
          label="允许主动领取"
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>
      </Space>
      <Alert
        type="info"
        message="商城券独立于历史优惠券；修改仅影响新发的券。整单退款返券，原有效期不延长。"
      />
    </RetailEditor>
  );
}
function IssueEditor({
  template,
  close,
}: {
  template: CouponTemplate;
  close: () => void;
}) {
  const [form] = Form.useForm();
  const key = useMutationKey();
  const [users, setUsers] = useState<
    { Id: number; NickName?: string; PhoneNumber?: string }[]
  >([]);
  const seq = useRef(0);
  const search = async (v: string) => {
    const token = ++seq.current;
    if (!v.trim()) return;
    try {
      const r = await call<{
        Items: { Id: number; NickName?: string; PhoneNumber?: string }[];
      }>('recipients', 'GET', { Keyword: v.trim() });
      if (token === seq.current) setUsers(r.Items || []);
    } catch (e) {
      message.error('用户搜索失败');
    }
  };
  return (
    <RetailEditor
      title={`发放：${template.Name}`}
      form={form}
      initialValues={{}}
      onClose={close}
      onSave={async (v) => {
        const data = { TemplateID: template.ID, UserID: v.UserID };
        await call('coupons/issue', 'POST', { ...data, RequestKey: key(data) });
      }}
    >
      <Form.Item name="UserID" label="指定用户" rules={required}>
        <Select
          showSearch
          filterOption={false}
          onSearch={search}
          placeholder="昵称、完整手机号或 #用户编号"
          options={users.map((u) => ({
            value: u.Id,
            label: `${u.NickName || '未设置昵称'} · ${u.PhoneNumber || ''} · #${
              u.Id
            }`,
          }))}
        />
      </Form.Item>
    </RetailEditor>
  );
}
function Settings() {
  const [form] = Form.useForm();
  const [policy, setPolicy] = useState<Policy>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function load() {
    try {
      const p = await call<Policy>('policy');
      setPolicy(p);
      form.setFieldsValue(p);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  return (
    <Card>
      {error && (
        <Alert
          type="error"
          message={error}
          action={<Button onClick={load}>重试</Button>}
        />
      )}
      <Form
        form={form}
        layout="vertical"
        disabled={!policy || busy}
        onFinish={async (v) => {
          setBusy(true);
          try {
            await call('policy', 'PUT', { ...policy, ...v });
            message.success('设置已保存');
            await load();
          } catch (e) {
            message.error((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
        style={{ maxWidth: 800 }}
      >
        <Space>
          <Form.Item name="Enabled" label="开启商城" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="Pickup" label="门店自提" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="Shipping" label="顺丰到付" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Space>
        <Form.Item name="ShippingServices" label="顺丰配送档位">
          <Checkbox.Group
            options={[
              { label: '普快', value: 'sf_standard' },
              { label: '特快', value: 'sf_express' },
              { label: '同城秒送', value: 'sf_local' },
            ]}
          />
        </Form.Item>
        <Form.Item name="Terms" label="订单约定">
          <Input.TextArea rows={5} maxLength={5000} />
        </Form.Item>
        <Space align="start">
          <Form.Item name="ReturnName" label="退货收件人">
            <Input maxLength={60} />
          </Form.Item>
          <Form.Item name="ReturnPhone" label="退货联系电话">
            <Input maxLength={30} />
          </Form.Item>
        </Space>
        <Form.Item name="ReturnAddress" label="退货地址">
          <Input.TextArea maxLength={500} />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={busy}>
          保存设置
        </Button>
      </Form>
    </Card>
  );
}
type Movement = {
  ID: number;
  Delta: number;
  Balance: number;
  Actor: string;
  Reason: string;
  OrderID: number;
  CreatedAt: string;
};
function StockHistory({
  stockID,
  title,
  close,
}: {
  stockID: number;
  title: string;
  close: () => void;
}) {
  const [page, setPage] = useState(1),
    [rows, setRows] = useState<Movement[]>([]),
    [total, setTotal] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setBusy(true);
    call<{ Movements: Movement[]; Total: number }>('stock/movements', 'GET', {
      StockID: stockID,
      Page: page,
    })
      .then((r) => {
        if (active) {
          setRows(r.Movements);
          setTotal(r.Total);
          setError('');
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [stockID, page, revision]);
  return (
    <Drawer
      open
      title={`${title} · 库存记录`}
      width={780}
      onClose={close}
      extra={<Button onClick={() => setRevision((v) => v + 1)}>刷新</Button>}
    >
      {error && <Alert type="error" message={error} />}
      <Table<Movement>
        rowKey="ID"
        loading={busy}
        dataSource={rows}
        pagination={{ current: page, pageSize: 20, total, onChange: setPage }}
        columns={[
          {
            title: '时间',
            dataIndex: 'CreatedAt',
            render: (v) => dayjs(v).format('YYYY/MM/DD HH:mm'),
          },
          {
            title: '变动',
            dataIndex: 'Delta',
            render: (v) => (v > 0 ? `+${v}` : v),
          },
          { title: '变动后可售', dataIndex: 'Balance' },
          { title: '原因', dataIndex: 'Reason' },
          { title: '订单', dataIndex: 'OrderID', render: (v) => v || '—' },
          { title: '操作员', dataIndex: 'Actor', render: (v) => v || '系统' },
        ]}
      />
    </Drawer>
  );
}

export default function RetailManagement() {
  const [history, setHistory] = useState<{ stockID: number; title: string }>();
  const [products, setProducts] = useState<Product[]>([]),
    [templates, setTemplates] = useState<CouponTemplate[]>([]),
    [page, setPage] = useState(1),
    [total, setTotal] = useState(0),
    [keyword, setKeyword] = useState(''),
    [revision, setRevision] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const seq = useRef(0);
  const [stock, setStock] = useState<{ sku: SKU; name: string }>(),
    [template, setTemplate] = useState<Partial<CouponTemplate>>(),
    [issue, setIssue] = useState<CouponTemplate>();
  const reload = () => setRevision((v) => v + 1);
  useEffect(() => {
    const token = ++seq.current;
    setBusy(true);
    Promise.all([
      call<{ Products: Product[]; Total: number }>('products', 'GET', {
        Page: page,
        Keyword: keyword,
      }),
      call<{ Templates: CouponTemplate[] }>('coupon-templates'),
    ])
      .then(([p, c]) => {
        if (token !== seq.current) return;
        setProducts(p.Products);
        setTotal(p.Total);
        setTemplates(c.Templates);
        setError('');
      })
      .catch((e) => {
        if (token === seq.current) setError(e.message);
      })
      .finally(() => {
        if (token === seq.current) setBusy(false);
      });
    return () => {
      seq.current++;
    };
  }, [page, keyword, revision]);
  return (
    <PageContainer
      title="门店商城管理"
      extra={<Button onClick={reload}>刷新</Button>}
    >
      {error && <Alert type="error" message={error} />}
      <Tabs
        items={[
          {
            key: 'stock',
            label: '价格与库存',
            children: (
              <Card>
                <Input.Search
                  placeholder="搜索商品"
                  allowClear
                  onSearch={(v) => {
                    setPage(1);
                    setKeyword(v);
                  }}
                  style={{ maxWidth: 360, marginBottom: 16 }}
                />
                <Table<Product>
                  rowKey="ID"
                  loading={busy}
                  dataSource={products}
                  pagination={{
                    current: page,
                    pageSize: 20,
                    total,
                    onChange: setPage,
                  }}
                  columns={[
                    { title: '商品', dataIndex: 'Name', width: 250 },
                    {
                      title: '商品状态',
                      width: 100,
                      dataIndex: 'Enabled',
                      render: (v) => (v ? '可售' : '已停用'),
                    },
                    {
                      title: '规格与本店库存',
                      width: 420,
                      render: (_, p) => (
                        <Space direction="vertical" style={{ width: '100%' }}>
                          {p.Offers.map((s) => (
                            <Space key={s.ID} wrap>
                              <span>{s.Name}</span>
                              <span>{money(s.Price)}</span>
                              <span>可售 {s.Available}</span>
                              <span>{s.OnSale ? '已上架' : '未上架'}</span>
                              <Button
                                type="link"
                                onClick={() =>
                                  setStock({ sku: s, name: p.Name })
                                }
                              >
                                调整
                              </Button>
                              {s.StockID > 0 && (
                                <Button
                                  type="link"
                                  onClick={() =>
                                    setHistory({
                                      stockID: s.StockID,
                                      title: `${p.Name} · ${s.Name}`,
                                    })
                                  }
                                >
                                  库存记录
                                </Button>
                              )}
                            </Space>
                          ))}
                        </Space>
                      ),
                    },
                  ]}
                />
              </Card>
            ),
          },
          {
            key: 'coupons',
            label: '商城优惠券',
            children: (
              <Card
                extra={
                  <Button type="primary" onClick={() => setTemplate({})}>
                    新建立减券
                  </Button>
                }
              >
                <Table<CouponTemplate>
                  rowKey="ID"
                  dataSource={templates}
                  columns={[
                    { title: '名称', dataIndex: 'Name' },
                    {
                      title: '优惠',
                      render: (_, c) =>
                        `满${money(c.Minimum)}减${money(c.Amount)}`,
                    },
                    {
                      title: '已发／总量',
                      render: (_, c) => `${c.Issued} / ${c.TotalLimit}`,
                    },
                    {
                      title: '截止',
                      dataIndex: 'EndsAt',
                      render: (v) => dayjs(v).format('YYYY/MM/DD HH:mm'),
                    },
                    {
                      title: '操作',
                      render: (_, c) => (
                        <Space>
                          <Button type="link" onClick={() => setTemplate(c)}>
                            编辑
                          </Button>
                          <Button
                            type="link"
                            disabled={!c.Enabled}
                            onClick={() => setIssue(c)}
                          >
                            发给用户
                          </Button>
                        </Space>
                      ),
                    },
                  ]}
                />
              </Card>
            ),
          },
          { key: 'settings', label: '营业与履约设置', children: <Settings /> },
        ]}
      />
      {history && (
        <StockHistory {...history} close={() => setHistory(undefined)} />
      )}
      {stock && (
        <StockEditor
          {...stock}
          close={() => setStock(undefined)}
          saved={reload}
        />
      )}
      {template && (
        <CouponEditor
          template={template}
          close={() => setTemplate(undefined)}
          saved={reload}
        />
      )}
      {issue && (
        <IssueEditor
          template={issue}
          close={() => {
            setIssue(undefined);
            reload();
          }}
        />
      )}
    </PageContainer>
  );
}
