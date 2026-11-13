import { useEffect, useRef, useState } from 'react';
import { PageContainer } from '@ant-design/pro-components';
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Descriptions,
  Drawer,
  Form,
  Input,
  InputNumber,
  message,
  Select,
  Space,
  Tabs,
  Typography,
} from 'antd';
import { history, useModel } from '@umijs/max';
import dayjs from 'dayjs';
import { Table } from '@/components/AdaptiveTable';
import RetailEditor, { useMutationKey } from '@/components/RetailEditor';
import {
  AfterSale,
  afterSaleStatuses,
  call,
  money,
  Order,
  OrderDetail,
  statuses,
} from '@/services/retail';
import { getCurrentStoreId } from '@/utils/pageStores';

const required = [{ required: true, message: '请填写' }];
function AfterSaleItems({
  detail,
  afterSale,
}: {
  detail: OrderDetail;
  afterSale: AfterSale;
}) {
  return (
    <Space direction="vertical" style={{ width: '100%', marginBottom: 16 }}>
      {afterSale.Lines.map((part) => {
        const line = detail.Order.Lines.find((l) => l.ID === part.OrderLineID);
        return (
          <div
            key={part.ID}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: 16,
            }}
          >
            <span>
              {line?.ProductName || '原订单商品'} · {line?.SKUName} ×{' '}
              {part.Quantity}
            </span>
            <span style={{ whiteSpace: 'nowrap' }}>{money(part.Amount)}</span>
          </div>
        );
      })}
    </Space>
  );
}
function Operation({
  detail,
  action,
  afterSale,
  close,
  saved,
}: {
  detail: OrderDetail;
  action: string;
  afterSale?: AfterSale;
  close: () => void;
  saved: () => void;
}) {
  const [form] = Form.useForm();
  const key = useMutationKey();
  const names: Record<string, string> = {
    ship: '确认顺丰发货',
    pickup: '核验提货码',
    approve: '审核通过',
    reject: '拒绝售后',
    receive_return: '确认退货验收',
  };
  return (
    <RetailEditor
      title={names[action]}
      form={form}
      initialValues={{
        Items: afterSale?.Lines.map((l) => ({
          OrderLineID: l.OrderLineID,
          Restock: false,
        })),
      }}
      onClose={close}
      onSave={async (v) => {
        const data = afterSale
          ? {
              ...v,
              AfterSaleID: afterSale.ID,
              Version: afterSale.Version,
              Action: action,
            }
          : {
              ...v,
              OrderID: detail.Order.ID,
              Version: detail.Order.Version,
              Action: action,
            };
        await call(afterSale ? 'after-sales/review' : 'action', 'POST', {
          ...data,
          RequestKey: key(data),
        });
        saved();
      }}
    >
      {action === 'ship' && (
        <Form.Item name="TrackingNumber" label="顺丰运单号" rules={required}>
          <Input maxLength={100} />
        </Form.Item>
      )}
      {action === 'pickup' && (
        <Form.Item name="PickupCode" label="顾客提供的提货码" rules={required}>
          <Input maxLength={16} />
        </Form.Item>
      )}
      {afterSale && (
        <p>
          申请退回 {money(afterSale.Amount)} ·{' '}
          {afterSale.Kind === 'return_refund' ? '退货退款' : '仅退款'}
        </p>
      )}
      {afterSale && <AfterSaleItems detail={detail} afterSale={afterSale} />}
      {action === 'approve' && (
        <Alert
          style={{ marginBottom: 16 }}
          type="info"
          message={
            afterSale?.Kind === 'return_refund'
              ? '通过后等待顾客退货，验收后再退款。'
              : '通过后将发起原路退款，到账结果以支付平台确认为准。'
          }
        />
      )}
      {action === 'receive_return' && (
        <Form.List name="Items">
          {(fields) =>
            fields.map((f, i) => (
              <div key={f.key}>
                <p>
                  {
                    detail.Order.Lines.find(
                      (l) => l.ID === afterSale?.Lines[i].OrderLineID
                    )?.ProductName
                  }{' '}
                  × {afterSale?.Lines[i].Quantity}
                </p>
                <Form.Item name={[f.name, 'OrderLineID']} hidden>
                  <InputNumber />
                </Form.Item>
                <Form.Item name={[f.name, 'Restock']} valuePropName="checked">
                  <Checkbox>实物完好，退款完成后回补可售库存</Checkbox>
                </Form.Item>
              </div>
            ))
          }
        </Form.List>
      )}
      <Form.Item
        name="Note"
        label={action === 'reject' ? '拒绝原因' : '处理说明（选填）'}
        rules={action === 'reject' ? required : undefined}
      >
        <Input.TextArea maxLength={500} />
      </Form.Item>
    </RetailEditor>
  );
}
export default function RetailOrders() {
  const params = new URLSearchParams(location.search);
  const [page, setPage] = useState(Number(params.get('page')) || 1),
    [status, setStatus] = useState(params.get('status') || ''),
    [orderID, setOrderID] = useState<number>(),
    [revision, setRevision] = useState(0),
    [orders, setOrders] = useState<Order[]>([]),
    [cases, setCases] = useState<AfterSale[]>([]),
    [total, setTotal] = useState(0),
    [casePage, setCasePage] = useState(1),
    [caseTotal, setCaseTotal] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const [detail, setDetail] = useState<OrderDetail>(),
    [operation, setOperation] = useState<{
      action: string;
      afterSale?: AfterSale;
    }>();
  const seq = useRef(0),
    detailSeq = useRef(0);
  const { initialState } = useModel('@@initialState');
  const grants =
    initialState?.auth?.Stores.find((s) => s.Id === getCurrentStoreId())
      ?.Pages || [];
  const canRefund =
    grants.includes('refunds') && grants.includes('retail-management');
  const reload = () => setRevision((v) => v + 1);
  async function open(id: number) {
    const token = ++detailSeq.current;
    try {
      const d = await call<OrderDetail>(`orders/${id}`);
      if (token === detailSeq.current) setDetail(d);
    } catch (e) {
      message.error((e as Error).message);
    }
  }
  useEffect(() => {
    history.replace({
      pathname: location.pathname,
      search: `?page=${page}&status=${encodeURIComponent(status)}`,
    });
    const token = ++seq.current;
    setBusy(true);
    Promise.all([
      call<{ Orders: Order[]; Total: number }>('orders', 'GET', {
        Page: page,
        Status: status,
        OrderID: orderID,
      }),
      call<{ AfterSales: AfterSale[]; Total: number }>('after-sales', 'GET', {
        Page: casePage,
      }),
    ])
      .then(([o, a]) => {
        if (token !== seq.current) return;
        setOrders(o.Orders);
        setTotal(o.Total);
        setCases(a.AfterSales);
        setCaseTotal(a.Total);
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
  }, [page, status, orderID, casePage, revision]);
  const refreshDetail = () => {
    reload();
    if (detail) void open(detail.Order.ID);
  };
  return (
    <PageContainer
      title="商城订单"
      extra={<Button onClick={reload}>刷新</Button>}
    >
      {error && <Alert type="error" message={error} />}
      <Tabs
        items={[
          {
            key: 'orders',
            label: '订单',
            children: (
              <Card>
                <Space style={{ marginBottom: 16 }} wrap>
                  <Select
                    value={status}
                    style={{ width: 150 }}
                    onChange={(v) => {
                      setPage(1);
                      setStatus(v);
                    }}
                    options={[
                      { value: '', label: '全部状态' },
                      ...Object.entries(statuses).map(([value, label]) => ({
                        value,
                        label,
                      })),
                    ]}
                  />
                  <Input.Search
                    placeholder="订单编号"
                    onSearch={(v) => {
                      setPage(1);
                      setOrderID(Number(v) || undefined);
                    }}
                  />
                </Space>
                <Table<Order>
                  rowKey="ID"
                  loading={busy}
                  dataSource={orders}
                  pagination={{
                    current: page,
                    pageSize: 20,
                    total,
                    onChange: setPage,
                  }}
                  columns={[
                    { title: '编号', dataIndex: 'ID', width: 90 },
                    {
                      title: '商品',
                      render: (_, o) =>
                        o.Lines.map(
                          (l) =>
                            `${l.ProductName} · ${l.SKUName} × ${l.Quantity}`
                        ).join('；'),
                      width: 320,
                    },
                    { title: '订单金额', dataIndex: 'Amount', render: money },
                    {
                      title: '状态',
                      dataIndex: 'Status',
                      render: (s) => statuses[s] || s,
                    },
                    {
                      title: '取货',
                      dataIndex: 'DeliveryMethod',
                      render: (v) => (v === 'pickup' ? '自提' : '顺丰到付'),
                    },
                    {
                      title: '下单时间',
                      dataIndex: 'CreatedAt',
                      render: (v) => dayjs(v).format('MM/DD HH:mm'),
                    },
                    {
                      title: '操作',
                      render: (_, o) => (
                        <Button type="link" onClick={() => open(o.ID)}>
                          处理订单
                        </Button>
                      ),
                    },
                  ]}
                />
              </Card>
            ),
          },
          {
            key: 'cases',
            label: '售后',
            children: (
              <Card>
                <Table<AfterSale>
                  rowKey="ID"
                  dataSource={cases}
                  pagination={{
                    current: casePage,
                    pageSize: 20,
                    total: caseTotal,
                    onChange: setCasePage,
                  }}
                  columns={[
                    { title: '售后编号', dataIndex: 'ID' },
                    { title: '订单', dataIndex: 'OrderID' },
                    {
                      title: '状态',
                      dataIndex: 'Status',
                      render: (s) => afterSaleStatuses[s] || s,
                    },
                    { title: '金额', dataIndex: 'Amount', render: money },
                    { title: '原因', dataIndex: 'Reason' },
                    {
                      title: '操作',
                      render: (_, a) => (
                        <Button type="link" onClick={() => open(a.OrderID)}>
                          查看处理
                        </Button>
                      ),
                    },
                  ]}
                />
              </Card>
            ),
          },
        ]}
      />
      <Drawer
        open={!!detail}
        width={780}
        title={detail ? `商城订单 #${detail.Order.ID}` : '订单详情'}
        onClose={() => {
          detailSeq.current++;
          setDetail(undefined);
        }}
        extra={<Button onClick={refreshDetail}>刷新</Button>}
      >
        {detail && (
          <Space direction="vertical" size={20} style={{ width: '100%' }}>
            <Card>
              <Typography.Title level={4}>
                {statuses[detail.Order.Status] || detail.Order.Status}
              </Typography.Title>
              <Space>
                {detail.Order.Status === 'paid' &&
                  !detail.AfterSales.some(
                    (a) => !['rejected', 'completed'].includes(a.Status)
                  ) && (
                    <Button
                      type="primary"
                      onClick={() =>
                        setOperation({
                          action:
                            detail.Order.DeliveryMethod === 'pickup'
                              ? 'pickup'
                              : 'ship',
                        })
                      }
                    >
                      {detail.Order.DeliveryMethod === 'pickup'
                        ? '核验自提'
                        : '填写发货'}
                    </Button>
                  )}
              </Space>
              <Descriptions
                column={2}
                style={{ marginTop: 16 }}
                items={[
                  {
                    key: 'subtotal',
                    label: '商品金额',
                    children: money(detail.Order.Subtotal),
                  },
                  {
                    key: 'discount',
                    label: '优惠',
                    children: money(detail.Order.Discount),
                  },
                  {
                    key: 'amount',
                    label: '订单应付',
                    children: money(detail.Order.Amount),
                  },
                  {
                    key: 'refund',
                    label: '已退款',
                    children: money(detail.Order.Refunded),
                  },
                  {
                    key: 'created',
                    label: '下单',
                    children: dayjs(detail.Order.CreatedAt).format(
                      'YYYY/MM/DD HH:mm'
                    ),
                  },
                ]}
              />
            </Card>
            <Card title="商品">
              <Table
                rowKey="ID"
                dataSource={detail.Order.Lines}
                pagination={false}
                columns={[
                  { title: '商品', dataIndex: 'ProductName', width: 200 },
                  { title: '规格', dataIndex: 'SKUName', width: 120 },
                  { title: '数量', dataIndex: 'Quantity', width: 60 },
                  {
                    title: '优惠后',
                    dataIndex: 'Amount',
                    render: money,
                    width: 100,
                  },
                  {
                    title: '已退数量',
                    dataIndex: 'RefundedQuantity',
                    width: 92,
                  },
                ]}
              />
            </Card>
            <Card title="履约资料">
              <Descriptions
                column={1}
                items={[
                  {
                    key: 'contact',
                    label: '联系人',
                    children: `${detail.Contact.Name} ${detail.Contact.Phone}`,
                  },
                  {
                    key: 'delivery',
                    label: '取货方式',
                    children:
                      detail.Order.DeliveryMethod === 'pickup'
                        ? '门店自提'
                        : `顺丰到付 · ${
                            {
                              sf_standard: '普快',
                              sf_express: '特快',
                              sf_local: '同城秒送',
                            }[detail.Contact.ShippingService] || ''
                          }`,
                  },
                  {
                    key: 'address',
                    label: '收货地址',
                    children: detail.Contact.Address || '到店自提',
                  },
                  {
                    key: 'tracking',
                    label: '运单号',
                    children: detail.Order.TrackingNumber || '尚未发货',
                  },
                  {
                    key: 'remark',
                    label: '买家备注',
                    children: detail.Order.Remark || '无',
                  },
                ]}
              />
            </Card>
            {detail.AfterSales.map((a) => (
              <Card
                key={a.ID}
                title={`售后 #${a.ID} · ${
                  afterSaleStatuses[a.Status] || a.Status
                }`}
              >
                <p>{a.Reason}</p>
                <AfterSaleItems detail={detail} afterSale={a} />
                <p>
                  {money(a.Amount)} ·{' '}
                  {a.Kind === 'return_refund' ? '退货退款' : '仅退款'}
                </p>
                {a.ReviewNote && <p>处理说明：{a.ReviewNote}</p>}
                {a.TrackingNumber && (
                  <p>
                    退货物流：{a.TrackingCompany} {a.TrackingNumber}
                  </p>
                )}
                {detail.Refunds.filter((r) => r.ID === a.RefundRequestID).map(
                  (r) => (
                    <Alert
                      key={r.ID}
                      type={r.Status === 'refund_failed' ? 'error' : 'info'}
                      message={
                        r.Status === 'refunded'
                          ? '退款已确认'
                          : r.Status === 'refund_failed'
                          ? '退款失败，可重试'
                          : '退款处理中'
                      }
                      description={r.RefundError}
                    />
                  )
                )}
                {canRefund && (
                  <Space style={{ marginTop: 16 }}>
                    {a.Status === 'pending_review' && (
                      <>
                        <Button
                          type="primary"
                          onClick={() =>
                            setOperation({ action: 'approve', afterSale: a })
                          }
                        >
                          通过
                        </Button>
                        <Button
                          onClick={() =>
                            setOperation({ action: 'reject', afterSale: a })
                          }
                        >
                          拒绝
                        </Button>
                      </>
                    )}
                    {['awaiting_return', 'returning'].includes(a.Status) && (
                      <Button
                        type="primary"
                        onClick={() =>
                          setOperation({
                            action: 'receive_return',
                            afterSale: a,
                          })
                        }
                      >
                        确认退货验收
                      </Button>
                    )}
                    {a.Status === 'refund_pending' &&
                      detail.Refunds.some(
                        (r) =>
                          r.ID === a.RefundRequestID &&
                          r.Status === 'refund_failed'
                      ) && (
                        <Button
                          onClick={async () => {
                            try {
                              await call(
                                `after-sales/${a.ID}/retry-refund`,
                                'POST',
                                {}
                              );
                              refreshDetail();
                            } catch (e) {
                              message.error((e as Error).message);
                            }
                          }}
                        >
                          重试原路退款
                        </Button>
                      )}
                  </Space>
                )}
              </Card>
            ))}
            <Card title="订单约定">
              <p style={{ whiteSpace: 'pre-wrap' }}>{detail.Order.Terms}</p>
            </Card>
          </Space>
        )}
      </Drawer>
      {operation && detail && (
        <Operation
          detail={detail}
          {...operation}
          close={() => setOperation(undefined)}
          saved={refreshDetail}
        />
      )}
    </PageContainer>
  );
}
