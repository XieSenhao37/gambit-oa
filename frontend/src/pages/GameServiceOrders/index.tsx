import { Table } from '@/components/AdaptiveTable';
import {
  actions,
  call,
  money,
  newRequestKey,
  Order,
  OrderDetail,
  states,
} from '@/services/gameServices';
import useGameServiceAccess from '@/services/useGameServiceAccess';
import { ReloadOutlined, WalletOutlined } from '@ant-design/icons';
import { PageContainer } from '@ant-design/pro-components';
import { history } from '@umijs/max';
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Drawer,
  Dropdown,
  Empty,
  Form,
  Image,
  Input,
  InputNumber,
  message,
  Modal,
  Popover,
  Select,
  Space,
  Spin,
  Tabs,
  Tag,
  Timeline,
  Typography,
} from 'antd';
import dayjs from 'dayjs';
import { useEffect, useRef, useState } from 'react';
import './index.less';
import {
  deliveryLabel,
  orderAction,
  orderActionLabel,
  readOrderFilters,
} from './presentation';
const refundStates: Record<string, string> = {
  pending_review: '待发起',
  refunding: '退款中',
  refunded: '已退款',
  refund_failed: '退款失败',
};
const time = (v?: string) => (v ? dayjs(v).format('MM-DD HH:mm') : '—');
export default function GameServiceOrders() {
  const { canManage, canRefund } = useGameServiceAccess();
  const [initialFilters] = useState(() =>
    readOrderFilters(window.location.search),
  );
  const [rows, setRows] = useState<Order[]>([]),
    [total, setTotal] = useState(0),
    [page, setPage] = useState(initialFilters.page),
    [status, setStatus] = useState(initialFilters.status),
    [kind, setKind] = useState(initialFilters.kind),
    [keyword, setKeyword] = useState(initialFilters.keyword),
    [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState({
    NetIncome: 0,
    DepositLiability: 0,
    PendingAccept: 0,
    PendingDelivery: 0,
    ReturnRequested: 0,
    DueToday: 0,
    Overdue: 0,
    RefundAttention: 0,
  });
  const [detail, setDetail] = useState<OrderDetail>(),
    [act, setAct] = useState(''),
    [saving, setSaving] = useState(false),
    [requestKey, setKey] = useState('');
  const [form] = Form.useForm();
  const [loadError, setLoadError] = useState(false);
  const [summaryReady, setSummaryReady] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(false);
  const detailRequest = useRef(0);
  const operationPending = useRef(false);
  const listRequest = useRef(0);
  const currentQuery = `${page}:${status}:${kind}:${keyword}`;
  const queryRef = useRef(currentQuery);
  queryRef.current = currentQuery;
  async function load() {
    const generation = ++listRequest.current;
    const query = currentQuery;
    setLoading(true);
    setLoadError(false);
    try {
      const r = await call<{
        Orders: Order[];
        Total: number;
        Summary: typeof summary;
      }>(
        `orders?Page=${page}&Status=${status}&Kind=${kind}&Keyword=${encodeURIComponent(
          keyword,
        )}`,
      );
      if (generation !== listRequest.current || query !== queryRef.current)
        return;
      setRows(r.Orders || []);
      setTotal(r.Total);
      setSummary(r.Summary);
      setSummaryReady(true);
    } catch {
      if (generation === listRequest.current && query === queryRef.current)
        setLoadError(true);
    } finally {
      if (generation === listRequest.current && query === queryRef.current)
        setLoading(false);
    }
  }
  useEffect(() => {
    void load();
    const query = new URLSearchParams(window.location.search);
    query.set('status', status);
    query.set('kind', kind);
    query.set('keyword', keyword);
    query.set('page', String(page));
    history.replace(`/game-service-orders?${query.toString()}`);
    return () => {
      listRequest.current++;
    };
  }, [page, status, kind, keyword]);
  useEffect(() => {
    const id = Number(
      new URLSearchParams(window.location.search).get('orderId'),
    );
    if (Number.isSafeInteger(id) && id > 0) void open(id);
  }, []);
  async function open(id: number) {
    const generation = ++detailRequest.current;
    setDetailOpen(true);
    setDetailLoading(true);
    setDetailError(false);
    try {
      const next = await call<OrderDetail>(`orders/${id}`);
      if (generation === detailRequest.current) setDetail(next);
    } catch {
      if (generation === detailRequest.current) setDetailError(true);
    } finally {
      if (generation === detailRequest.current) setDetailLoading(false);
    }
  }
  function closeDetail() {
    if (saving) return;
    detailRequest.current++;
    setDetailOpen(false);
    setDetail(undefined);
    setDetailLoading(false);
    setDetailError(false);
    const query = new URLSearchParams(window.location.search);
    query.delete('orderId');
    history.replace(`/game-service-orders?${query.toString()}`);
  }
  async function quickAction(row: Order) {
    const generation = ++detailRequest.current;
    setDetailOpen(true);
    setDetailLoading(true);
    setDetailError(false);
    setDetail(undefined);
    try {
      const next = await call<OrderDetail>(`orders/${row.ID}`);
      if (generation !== detailRequest.current) return;
      setDetail(next);
      const nextAction = orderAction(next.Order);
      if (nextAction) action(nextAction, next);
      else message.info('订单状态已更新，请核对后操作');
    } catch {
      if (generation === detailRequest.current) setDetailError(true);
    } finally {
      if (generation === detailRequest.current) setDetailLoading(false);
    }
  }
  function action(a: string, target = detail) {
    if (operationPending.current) return;
    setAct(a);
    setKey(newRequestKey());
    form.resetFields();
    form.setFieldsValue({
      Remark: '',
      TrackingCompany: target?.Contact?.ShippingService
        ? target.Contact.ShippingService === 'sf_local'
          ? '顺丰同城'
          : '顺丰速运'
        : '',
      Retained: 0,
      Lines: target?.Order.Lines.map((l) => ({
        LineID: l.ID,
        Quantity:
          a === 'return' || a === 'declare_loss'
            ? l.Quantity - l.Returned - l.Lost - (l.Bought || 0)
            : l.Returned - l.Inspected,
        Damaged: 0,
      })),
    });
  }
  async function submit(values: any) {
    if (!detail || operationPending.current) return;
    operationPending.current = true;
    setSaving(true);
    try {
      await call('action', 'POST', {
        ...values,
        OrderID: detail.Order.ID,
        Version: detail.Order.Version,
        Action: act,
        RequestKey: requestKey,
        Retained: Math.round((values.Retained || 0) * 100),
        Lines: (values.Lines || []).filter((l: any) => l.Quantity > 0),
      });
      message.success(
        act === 'return_complete'
          ? '已确认归还，押金将自动原路退回'
          : act === 'accept' && detail.Order.Status === 'pending_confirm'
          ? '已确认，等待玩家付款'
          : '操作已完成',
      );
      setAct('');
      window.dispatchEvent(new Event('game-order-updated'));
      await open(detail.Order.ID);
      await load();
    } finally {
      operationPending.current = false;
      setSaving(false);
    }
  }
  async function refund(id: number, status: string) {
    if (!detail || operationPending.current) return;
    operationPending.current = true;
    setSaving(true);
    try {
      await call('refund', 'POST', {
        RefundRequestID: id,
        Action: status === 'refunding' ? 'reconcile' : 'approve',
      });
      message.success('退款已处理，请核对最终状态');
      window.dispatchEvent(new Event('game-order-updated'));
      await open(detail.Order.ID);
      await load();
    } finally {
      operationPending.current = false;
      setSaving(false);
    }
  }
  const o = detail?.Order;
  const buttons =
    o?.Kind === 'buyout'
      ? []
      : ['pending_confirm', 'pending_accept'].includes(o?.Status || '')
      ? ['accept', 'reject']
      : o?.Status === 'accepted'
      ? ['dispatch', 'cancel']
      : o?.Status === 'rented'
      ? ['return_complete', 'return', 'declare_loss']
      : o?.Status === 'inspection'
      ? [
          'return_complete',
          'return',
          'inspect',
          'declare_loss',
          'settle_deposit',
        ]
      : o?.Kind === 'purchase' && o.Status === 'completed'
      ? ['purchase_return']
      : o?.Kind === 'purchase' &&
        ['refund_pending', 'refunded'].includes(o.Status)
      ? ['inspect']
      : [];
  return (
    <PageContainer
      title="桌游租售订单"
      extra={
        <Space>
          <Popover
            trigger="click"
            title="当前门店租售汇总"
            content={
              <div className="oa-order-finance">
                <span>累计净收入（含赔偿）</span>
                <strong>{summaryReady ? money(summary.NetIncome) : '—'}</strong>
                <span>待退押金（非收入）</span>
                <strong>
                  {summaryReady ? money(summary.DepositLiability) : '—'}
                </strong>
              </div>
            }
          >
            <Button icon={<WalletOutlined />}>财务汇总</Button>
          </Popover>
          <Button
            icon={<ReloadOutlined />}
            loading={loading}
            onClick={() => void load()}
          >
            刷新
          </Button>
        </Space>
      }
    >
      <div className="oa-order-filters" aria-label="租售订单快捷筛选">
        <button
          type="button"
          className={status === 'todo' ? 'is-active' : ''}
          aria-pressed={status === 'todo'}
          onClick={() => {
            setStatus('todo');
            setPage(1);
          }}
        >
          全部待办
        </button>
        {[
          ['待确认', summary.PendingAccept, 'pending_confirmation'],
          ['待交付', summary.PendingDelivery, 'accepted'],
          ['归还待处理', summary.ReturnRequested, 'return_requested'],
          ['今日应还', summary.DueToday, 'due_today'],
          ['已逾期', summary.Overdue, 'overdue'],
          ['退款待处理', summary.RefundAttention, 'refund_attention'],
        ].map(([label, count, value]) => (
          <button
            key={String(value)}
            type="button"
            className={`${status === value ? 'is-active' : ''} ${
              value === 'overdue' && Number(count) > 0 ? 'has-warning' : ''
            }`}
            aria-pressed={status === value}
            onClick={() => {
              setStatus(String(value));
              setPage(1);
            }}
          >
            {label}
            <span>{summaryReady ? count : '—'}</span>
          </button>
        ))}
      </div>
      <div className="oa-panel oa-order-list-panel">
        <div className="oa-order-toolbar">
          <Input.Search
            key={initialFilters.keyword}
            defaultValue={initialFilters.keyword}
            placeholder="姓名、手机号、桌游或订单号"
            allowClear
            onSearch={(value) => {
              setKeyword(value.trim());
              setPage(1);
            }}
          />
          <Select
            aria-label="订单类型"
            value={kind}
            onChange={(value) => {
              setKind(value);
              setPage(1);
            }}
            options={[
              { value: '', label: '全部类型' },
              { value: 'rental', label: '租赁' },
              { value: 'purchase', label: '购买' },
              { value: 'buyout', label: '租转购' },
            ]}
          />
          <Select
            aria-label="订单状态"
            value={status}
            onChange={(value) => {
              setStatus(value);
              setPage(1);
            }}
            options={[
              { value: 'todo', label: '全部待办' },
              { value: '', label: '全部订单' },
              { value: 'pending_confirmation', label: '待确认' },
              { value: 'return_requested', label: '归还待处理' },
              { value: 'due_today', label: '今日应还' },
              { value: 'overdue', label: '已逾期' },
              { value: 'refund_attention', label: '退款待处理' },
              ...Object.entries(states).map(([value, label]) => ({
                value,
                label,
              })),
            ]}
          />
          <span className="oa-secondary">
            {!loading && !loadError ? `共 ${total} 单` : ''}
          </span>
        </div>
        {loadError && (
          <Alert
            showIcon
            type="error"
            message="列表未能更新，当前内容可能已过时。"
            action={<Button onClick={() => void load()}>重试</Button>}
            style={{ marginBottom: 16 }}
          />
        )}
        <Table<Order>
          rowKey="ID"
          loading={loading}
          dataSource={rows}
          locale={{
            emptyText: (
              <Empty
                description="没有符合条件的订单"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            ),
          }}
          pagination={{
            current: page,
            pageSize: 30,
            total,
            onChange: setPage,
            showSizeChanger: false,
          }}
          columns={[
            {
              title: '订单 / 玩家',
              width: 160,
              render: (_, row) => (
                <div>
                  <Button
                    type="link"
                    className="oa-order-number"
                    onClick={() => void open(row.ID)}
                  >
                    #{row.ID} ·{' '}
                    {row.Kind === 'rental'
                      ? '租赁'
                      : row.Kind === 'buyout'
                      ? '租转购'
                      : '购买'}
                  </Button>
                  <div>{row.ContactName || '未填写姓名'}</div>
                  {row.ContactPhone && (
                    <Typography.Text className="oa-secondary" copyable>
                      {row.ContactPhone}
                    </Typography.Text>
                  )}
                  <div className="oa-secondary">{time(row.CreatedAt)}</div>
                </div>
              ),
            },
            {
              title: '桌游',
              width: 190,
              render: (_, row) => (
                <div className="oa-order-games">
                  {row.Lines.slice(0, 2).map((line) => (
                    <div key={line.ID}>
                      <strong>
                        {line.GameName} × {line.Quantity}
                      </strong>
                      {line.Condition && (
                        <div className="oa-secondary">{line.Condition}</div>
                      )}
                    </div>
                  ))}
                  {row.Lines.length > 2 && (
                    <Button type="link" onClick={() => void open(row.ID)}>
                      另有 {row.Lines.length - 2} 款
                    </Button>
                  )}
                </div>
              ),
            },
            {
              title: '状态',
              width: 100,
              render: (_, row) => (
                <Tag
                  color={
                    row.Status === 'pending_confirm' ||
                    row.Status === 'pending_accept'
                      ? 'gold'
                      : row.Status === 'completed' || row.Status === 'refunded'
                      ? 'green'
                      : undefined
                  }
                >
                  {states[row.Status] || row.Status}
                </Tag>
              ),
            },
            {
              title: '取货 / 租期',
              width: 150,
              render: (_, row) => (
                <>
                  <div>
                    {row.DeliveryMethod === 'shipping'
                      ? '快递到付'
                      : '门店自提'}
                  </div>
                  {row.Kind === 'rental' && (
                    <div className="oa-secondary oa-rental-period">
                      <span>
                        {dayjs(row.StartDate).format('M月D日')}–
                        {dayjs(row.EndDate).format('M月D日')}
                      </span>
                      <span>{row.Days}天</span>
                    </div>
                  )}
                  {row.ReturnRequestedAt &&
                    ['rented', 'inspection'].includes(row.Status) && (
                      <Tag>已申请归还</Tag>
                    )}
                </>
              ),
            },
            {
              title: '订单金额',
              width: 130,
              align: 'right',
              render: (_, row) => (
                <>
                  <strong className="oa-order-money">
                    {money(row.Amount)}
                  </strong>
                  {row.DepositAmount > 0 && (
                    <div className="oa-secondary">
                      含押金 {money(row.DepositAmount)}
                    </div>
                  )}
                </>
              ),
            },
            {
              title: '操作',
              width: 140,
              fixed: 'right',
              render: (_, row) => (
                <Space>
                  {orderAction(row) && (
                    <Button
                      disabled={loading || loadError || detailLoading || saving}
                      type="primary"
                      onClick={() => void quickAction(row)}
                    >
                      {orderActionLabel(row)}
                    </Button>
                  )}
                  {!orderAction(row) && (
                    <Button type="text" onClick={() => void open(row.ID)}>
                      查看
                    </Button>
                  )}
                </Space>
              ),
            },
          ]}
        />
      </div>
      <Drawer
        width={880}
        rootClassName="oa-order-detail"
        title={
          o
            ? `桌游${
                o.Kind === 'rental'
                  ? '租赁'
                  : o.Kind === 'buyout'
                  ? '租转购补款'
                  : '购买'
              }订单 #${o.ID}`
            : ''
        }
        open={detailOpen}
        onClose={closeDetail}
        maskClosable={!saving}
        closable={!saving}
        extra={
          <Button
            disabled={saving || detailLoading}
            onClick={() => o && open(o.ID)}
          >
            刷新状态
          </Button>
        }
      >
        {detailLoading ? (
          <Spin style={{ display: 'block', margin: '48px auto' }} />
        ) : detailError ? (
          <Alert type="error" message="订单未能更新，请关闭后重新打开。" />
        ) : (
          o &&
          detail && (
            <>
              {o.ReturnRequestedAt &&
                ['rented', 'inspection'].includes(o.Status) && (
                  <Alert
                    style={{ marginBottom: 16 }}
                    message={`客户已申请${
                      o.ReturnMethod === 'shipping'
                        ? '邮寄归还'
                        : o.ReturnMethod === 'pickup'
                        ? '到店归还'
                        : '归还'
                    } ${o.ReturnTrackingCompany || ''} ${
                      o.ReturnTrackingNumber || ''
                    }`}
                    type="info"
                  />
                )}
              <div className="oa-order-detail-heading">
                <Space wrap>
                  <Tag color="blue">{states[o.Status]}</Tag>
                  {buttons
                    .filter(
                      (a) =>
                        ![
                          'return',
                          'inspect',
                          'declare_loss',
                          'settle_deposit',
                          'purchase_return',
                        ].includes(a) &&
                        (canManage ||
                          ![
                            'settle_deposit',
                            'purchase_return',
                            'declare_loss',
                          ].includes(a)),
                    )
                    .map((a) => (
                      <Button
                        key={a}
                        disabled={saving || detailLoading}
                        type={
                          a === 'accept' ||
                          a === 'dispatch' ||
                          a === 'return_complete'
                            ? 'primary'
                            : 'default'
                        }
                        danger={a === 'reject' || a === 'cancel'}
                        onClick={() => action(a)}
                      >
                        {actions[a] || '登记购买退回'}
                      </Button>
                    ))}
                  {buttons.some((a) =>
                    [
                      'return',
                      'inspect',
                      'declare_loss',
                      'settle_deposit',
                      'purchase_return',
                    ].includes(a),
                  ) && (
                    <Dropdown
                      menu={{
                        items: buttons
                          .filter(
                            (a) =>
                              [
                                'return',
                                'inspect',
                                'declare_loss',
                                'settle_deposit',
                                'purchase_return',
                              ].includes(a) &&
                              (canManage || ['return', 'inspect'].includes(a)),
                          )
                          .map((a) => ({ key: a, label: actions[a] })),
                        onClick: ({ key }) => action(key),
                      }}
                    >
                      <Button>异常／分批处理</Button>
                    </Dropdown>
                  )}
                </Space>
              </div>
              {o.Status === 'awaiting_payment' && o.PaymentExpiresAt && (
                <p className="oa-secondary">
                  付款截止 {time(o.PaymentExpiresAt)}
                </p>
              )}
              {o.Remark && (
                <p className="oa-order-note">
                  {o.Status === 'cancelled' ? '取消原因' : '门店备注'}：
                  {o.Remark}
                </p>
              )}
              <section className="oa-order-detail-section">
                <h3>商品与履约</h3>
                {o.Lines.map((line) => (
                  <div key={line.ID} className="oa-order-product">
                    {line.CoverURL ? (
                      <Image
                        width={64}
                        height={64}
                        style={{ objectFit: 'contain', borderRadius: 8 }}
                        src={line.CoverURL}
                      />
                    ) : (
                      <div className="oa-order-cover-empty" />
                    )}
                    <div className="oa-order-product-info">
                      <strong>{line.GameName}</strong>
                      <div className="oa-secondary">
                        {[line.Condition, line.Description]
                          .filter(Boolean)
                          .join(' · ')}
                      </div>
                      <div className="oa-secondary">
                        {[
                          line.Returned ? `已归还 ${line.Returned}` : '',
                          line.Inspected ? `已检查 ${line.Inspected}` : '',
                          line.Damaged ? `损坏保留 ${line.Damaged}` : '',
                          line.Lost ? `遗失 ${line.Lost}` : '',
                          line.Bought ? `已购买 ${line.Bought}` : '',
                        ]
                          .filter(Boolean)
                          .join(' · ')}
                      </div>
                    </div>
                    <strong>×{line.Quantity}</strong>
                  </div>
                ))}
                {o.Kind === 'rental' && (
                  <p className="oa-secondary">
                    {o.StartDate} 至 {o.EndDate} · {o.Days}天
                  </p>
                )}
                <Descriptions
                  column={1}
                  size="small"
                  items={[
                    {
                      label: '取货方式',
                      children: deliveryLabel(
                        o.DeliveryMethod,
                        detail.Contact?.ShippingService,
                      ),
                    },
                    {
                      label: '联系人',
                      children: (
                        <Space wrap>
                          <span>{detail.Contact?.Name}</span>
                          {detail.Contact?.Phone && (
                            <Typography.Text copyable>
                              {detail.Contact.Phone}
                            </Typography.Text>
                          )}
                        </Space>
                      ),
                    },
                    ...(detail.Contact?.Address
                      ? [
                          {
                            label: '收货地址',
                            children: (
                              <Typography.Text copyable>
                                {detail.Contact.Address}
                              </Typography.Text>
                            ),
                          },
                        ]
                      : []),
                    ...(o.TrackingNumber
                      ? [
                          {
                            label: '发货物流',
                            children: (
                              <Typography.Text copyable>
                                {o.TrackingCompany} {o.TrackingNumber}
                              </Typography.Text>
                            ),
                          },
                        ]
                      : []),
                  ]}
                />
              </section>
              <section className="oa-order-detail-section">
                <h3>费用明细</h3>
                <div className="oa-order-finance oa-order-fees">
                  <span>{o.Kind === 'rental' ? '租金' : '货款'}</span>
                  <strong>{money(o.ServiceAmount)}</strong>
                  {o.DepositAmount > 0 && (
                    <>
                      <span>押金（非收入）</span>
                      <strong>{money(o.DepositAmount)}</strong>
                    </>
                  )}
                  {o.DepositRetained > 0 && (
                    <>
                      <span>押金扣留</span>
                      <strong>{money(o.DepositRetained)}</strong>
                    </>
                  )}
                  {o.DepositApplied > 0 && (
                    <>
                      <span>押金已抵购款</span>
                      <strong>{money(o.DepositApplied)}</strong>
                    </>
                  )}
                  <span>订单金额</span>
                  <strong>{money(o.Amount)}</strong>
                  {o.RefundAmount > 0 && (
                    <>
                      <span>已退款</span>
                      <strong>{money(o.RefundAmount)}</strong>
                    </>
                  )}
                </div>
                {o.AcceptedStoreID && (
                  <p className="oa-secondary">款项归属接单门店</p>
                )}
              </section>
              <Tabs
                style={{ marginTop: 24 }}
                items={[
                  {
                    key: 'refund',
                    label: '退款与押金',
                    children: (
                      <>
                        <Alert
                          showIcon
                          type="info"
                          message="退款仅在微信结果确认后标为成功。押金与租金分开记录。"
                          style={{ marginBottom: 16 }}
                        />
                        <Table
                          rowKey="ID"
                          dataSource={detail.Refunds}
                          pagination={false}
                          columns={[
                            { title: '任务', dataIndex: 'ID' },
                            {
                              title: '金额',
                              dataIndex: 'Amount',
                              render: money,
                            },
                            {
                              title: '状态',
                              dataIndex: 'Status',
                              render: (v) =>
                                v === 'pending_review' && o?.AutoRefund
                                  ? '自动退款中'
                                  : refundStates[v] || v,
                            },
                            {
                              title: '说明',
                              render: (_, r) => (
                                <>
                                  {r.ReviewRemark}
                                  {r.RefundError && (
                                    <div style={{ color: '#cf1322' }}>
                                      {r.RefundError}
                                    </div>
                                  )}
                                </>
                              ),
                            },
                            {
                              title: '操作',
                              render: (_, r) =>
                                [
                                  'pending_review',
                                  'refund_failed',
                                  'refunding',
                                ].includes(r.Status) &&
                                canRefund &&
                                !(
                                  r.Status === 'pending_review' && o?.AutoRefund
                                ) ? (
                                  <Button
                                    loading={saving}
                                    onClick={() =>
                                      Modal.confirm({
                                        title:
                                          r.Status === 'refunding'
                                            ? '查询微信退款结果'
                                            : '确认发起微信原路退款',
                                        content: `退款 ${money(
                                          r.Amount,
                                        )}，仅限此订单已创建的任务。`,
                                        onOk: () => refund(r.ID, r.Status),
                                      })
                                    }
                                  >
                                    {r.Status === 'refunding'
                                      ? '对账'
                                      : r.Status === 'refund_failed'
                                      ? '重试退款'
                                      : '发起退款'}
                                  </Button>
                                ) : null,
                            },
                          ]}
                        />
                      </>
                    ),
                  },
                  {
                    key: 'journal',
                    label: '操作记录',
                    children: (
                      <Timeline
                        items={detail.Journal.map((j) => ({
                          children: (
                            <>
                              <strong>{actions[j.Action] || j.Action}</strong> ·{' '}
                              {time(j.CreatedAt)}
                              <div>
                                操作人 #{j.Actor || '系统'} · {j.Remark}
                              </div>
                              {(j.ServiceAmount !== 0 ||
                                j.DepositAmount !== 0) && (
                                <span>
                                  租金／货款 {money(j.ServiceAmount)} · 押金{' '}
                                  {money(j.DepositAmount)}
                                </span>
                              )}
                            </>
                          ),
                        }))}
                      />
                    ),
                  },
                  {
                    key: 'terms',
                    label: '下单规则快照',
                    children: (
                      <Typography.Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                        {o.Terms || '下单时门店未提供额外规则'}
                      </Typography.Paragraph>
                    ),
                  },
                ]}
              />
            </>
          )
        )}
      </Drawer>
      <Modal
        rootClassName="oa-operation-modal"
        title={actions[act] || '登记购买退回'}
        okText={
          act === 'return_complete'
            ? '确认归还并退押金'
            : act === 'accept'
            ? '确认订单'
            : act === 'reject'
            ? '确认拒单'
            : act === 'dispatch'
            ? '确认交付'
            : '确认操作'
        }
        cancelText="取消"
        open={!!act}
        onCancel={() => {
          if (!operationPending.current) setAct('');
        }}
        maskClosable={!saving}
        closable={!saving}
        onOk={() => form.submit()}
        confirmLoading={saving}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={submit}>
          {act === 'return_complete' && (
            <Alert
              style={{ marginBottom: 16 }}
              type="info"
              message={`确认实物全部收到、配件齐全且完好。应退押金 ${money(
                o?.Lines.filter((l) => !l.Bought).reduce(
                  (n, l) => n + l.Deposit,
                  0,
                ) || 0,
              )}。确认后自动原路退回押金，无需再次操作。`}
            />
          )}
          {act === 'accept' && (
            <Alert
              type="info"
              showIcon
              message={
                o?.Status === 'pending_confirm'
                  ? '确认后锁定库存24小时，等待玩家付款。未付款不可交付；超时关单后释放预留。'
                  : '接单将预留库存，并将租金／货款及押金归属当前门店。'
              }
              style={{ marginBottom: 20 }}
            />
          )}
          {act === 'dispatch' && o?.DeliveryMethod === 'shipping' && (
            <>
              <Form.Item
                name="TrackingCompany"
                label="快递公司"
                rules={[{ required: true }]}
              >
                <Input
                  maxLength={60}
                  readOnly={!!detail?.Contact?.ShippingService}
                />
              </Form.Item>
              <Form.Item
                name="TrackingNumber"
                label="运单号"
                rules={[{ required: true }]}
              >
                <Input maxLength={80} />
              </Form.Item>
            </>
          )}
          {(act === 'return' ||
            act === 'inspect' ||
            act === 'declare_loss') && (
            <Form.List name="Lines">
              {(fields) => (
                <>
                  {fields.map((f, i) => (
                    <Card
                      key={f.key}
                      size="small"
                      title={o?.Lines[i]?.GameName}
                      style={{ marginBottom: 12 }}
                    >
                      <Form.Item hidden name={[f.name, 'LineID']}>
                        <InputNumber />
                      </Form.Item>
                      <Space>
                        <Form.Item
                          name={[f.name, 'Quantity']}
                          label={
                            act === 'return'
                              ? '本次实际收到'
                              : act === 'declare_loss'
                              ? '整盒遗失份数'
                              : '本次检查份数'
                          }
                        >
                          <InputNumber
                            min={0}
                            max={
                              act === 'return' || act === 'declare_loss'
                                ? (o?.Lines[i]?.Quantity || 0) -
                                  (o?.Lines[i]?.Returned || 0) -
                                  (o?.Lines[i]?.Lost || 0) -
                                  (o?.Lines[i]?.Bought || 0)
                                : (o?.Lines[i]?.Returned || 0) -
                                  (o?.Lines[i]?.Inspected || 0)
                            }
                            precision={0}
                          />
                        </Form.Item>
                        {act === 'inspect' && (
                          <Form.Item
                            name={[f.name, 'Damaged']}
                            label="其中损坏保留"
                          >
                            <InputNumber
                              min={0}
                              max={o?.Lines[i]?.Quantity}
                              precision={0}
                            />
                          </Form.Item>
                        )}
                      </Space>
                    </Card>
                  ))}
                </>
              )}
            </Form.List>
          )}
          {act === 'settle_deposit' && (
            <>
              <Alert
                type="warning"
                message={`全部检查后结算，押金 ${money(
                  o?.DepositAmount || 0,
                )}。扣留部分需说明。`}
                style={{ marginBottom: 20 }}
              />
              <Form.Item
                name="Retained"
                label="扣留押金（元）"
                rules={[{ required: true }]}
              >
                <InputNumber
                  min={0}
                  max={(o?.DepositAmount || 0) / 100}
                  precision={2}
                />
              </Form.Item>
            </>
          )}
          {act === 'declare_loss' && (
            <Alert
              type="warning"
              showIcon
              message="仅登记确认无法找回的整盒桌游；会减少借出数量、对外额度和门店总数量。配件缺失请登记归还后按损坏检查处理，押金另行结算。"
              style={{ marginBottom: 16 }}
            />
          )}
          {act === 'purchase_return' && (
            <Alert
              type="warning"
              showIcon
              message="仅在实物已收回门店后操作：库存进入检查保留，并创建整单退款任务。"
              style={{ marginBottom: 20 }}
            />
          )}
          <Form.Item
            name="Remark"
            label={
              [
                'reject',
                'cancel',
                'inspect',
                'purchase_return',
                'declare_loss',
              ].includes(act)
                ? '操作说明'
                : '操作说明（选填）'
            }
            rules={
              [
                'reject',
                'cancel',
                'inspect',
                'purchase_return',
                'declare_loss',
              ].includes(act)
                ? [{ required: true }]
                : []
            }
          >
            <Input.TextArea
              autoSize={{ minRows: 2, maxRows: 4 }}
              maxLength={1000}
              placeholder={
                act === 'accept'
                  ? '如有特殊安排可填写，不填也可确认订单'
                  : '填写本次操作的补充说明'
              }
            />
          </Form.Item>
        </Form>
      </Modal>
    </PageContainer>
  );
}
