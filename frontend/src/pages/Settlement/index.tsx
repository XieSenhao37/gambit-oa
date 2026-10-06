import StoreSwitcher from '@/components/StoreSwitcher';
import {
  settlementExport,
  settlementGet,
  settlementPost,
} from '@/services/settlement';
import { PageContainer } from '@ant-design/pro-components';
import { useModel } from '@umijs/max';
import type { UploadFile } from 'antd';
import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Pagination,
  Progress,
  Radio,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd';
import dayjs from 'dayjs';
import { useEffect, useRef, useState } from 'react';
import CardPricing from './CardPricing';
import { metricLabel } from './MetricHelp';
import { ReceiptProof } from './ReceiptProof';
import ReportActions from './ReportActions';

const yuan = (v: number | null) =>
  v === null || v === undefined ? '待确认' : `¥${(v / 100).toFixed(2)}`;
const states: Record<string, string> = {
  draft: '待确认',
  confirmed: '已结算',
  void: '已作废',
  locked: '已结算（历史记录）',
  open: '分月结算中',
  closed: '全额处理完毕',
  allocated: '已按当月时长分配',
  carried: '当月无核销，暂留池内',
  estimate: '待生成报表',
  pending: '尚未履约',
  needs_cost: '待确认成本',
  ready: '资料已保存，待结算',
  posted: '已入账',
  cancelled: '已取消',
  valid: '有效',
  review: '待核验',
  excluded: '不参与分配',
  reserved: '已冻结',
  consumed: '已消耗',
  released: '已解冻',
  returned: '已退回',
};
const kinds: Record<string, string> = {
  wechat_play: '游玩微信收款',
  wechat_catering: '餐饮微信收款',
  wechat_refund: '微信消费退款',
  wallet: '储值消费',
  wallet_refund: '储值消费退款',
  month_card: '月卡当月分配',
  month_card_carry: '月卡暂留款补分',
  point_cost: '积分成本',
  adjustment: '结算调整',
  settlement_fee: '统一结算手续费',
  redeem: '积分兑换',
  raffle: '积分抽奖',
};
export default function Settlement() {
  const { initialState } = useModel('@@initialState');
  const hq = !!initialState?.auth?.Headquarters;
  const beijingMonth = dayjs(
    new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 7) + '-01',
  );
  const preference = `oa_settlement_view:${initialState?.auth?.UserId}`;
  const [month, setMonth] = useState(() => {
      const saved = dayjs(sessionStorage.getItem(`${preference}:month`) || '');
      return saved.isValid() && saved.isBefore(beijingMonth, 'month')
        ? saved
        : beijingMonth.subtract(1, 'month');
    }),
    [scope, setScope] = useState(
      hq
        ? sessionStorage.getItem(`${preference}:scope`) === 'store'
          ? 'store'
          : 'all'
        : 'store',
    ),
    [tab, setTab] = useState('overview');
  const [actionContainer, setActionContainer] = useState<HTMLDivElement | null>(
    null,
  );
  const [loadedOverview, setOverview] = useState<any>(),
    [loadedRows, setRows] = useState<any[]>([]),
    [total, setTotal] = useState(0),
    [loading, setLoading] = useState(false),
    [revision, setRevision] = useState(0),
    [page, setPage] = useState(1);
  const [loadedContext, setLoadedContext] = useState('');
  const [loadedOverviewKey, setLoadedOverviewKey] = useState('');
  const [entryFilters, setEntryFilters] = useState({
    Kind: '',
    Store: undefined as number | undefined,
    Start: '',
    End: '',
    Query: '',
    Sort: 'event_at',
    Order: 'desc',
  });
  const [entrySearch, setEntrySearch] = useState('');
  const changeEntryFilters = (values: Partial<typeof entryFilters>) => {
    setEntryFilters((old) => ({ ...old, ...values }));
    setPage(1);
  };
  const [loadError, setLoadError] = useState(false);
  const [rowsLoading, setRowsLoading] = useState(false);
  const [rowsError, setRowsError] = useState(false);
  const [rowsKey, setRowsKey] = useState('');
  const tabCache = useRef(new Map<string, any>());
  const [products, setProducts] = useState<any[]>([]);
  const storeName = (id: number) =>
    id === 0
      ? '总部'
      : initialState?.auth?.Stores.find((s) => s.Id === id)?.Name ||
        `门店 #${id}`;
  const sourceName = (key: string) =>
    key.startsWith('wallet:recharge:')
      ? `储值充值 #${key.split(':').pop()}`
      : key.startsWith('opening:point:')
      ? '历史积分期初'
      : key.startsWith('point:earn:')
      ? `消费赠分 · 支付单 #${key.split(':').pop()}`
      : key.startsWith('point:withdraw:')
      ? `店员发放 #${key.split(':').pop()}`
      : key.startsWith('profile_')
      ? '总部资料任务奖励'
      : key.startsWith('event:')
      ? `门店活动奖励 #${key.split(':').pop()}`
      : key;
  const [entryDetail, setEntryDetail] = useState<any>();
  const [costFiles, setCostFiles] = useState<UploadFile[]>([]);
  const [removeCostImage, setRemoveCostImage] = useState(false);
  const [savingEditor, setSavingEditor] = useState(false);
  const [detail, setDetail] = useState<any>(),
    [editor, setEditor] = useState<any>(),
    [form] = Form.useForm();
  const params = {
    Month: month.format('YYYY-MM'),
    Scope: scope,
    Current: page,
    PageSize: 20,
    ...(['overview', 'cash'].includes(tab)
      ? {
          EntryKind: entryFilters.Kind,
          EntryStoreId: entryFilters.Store,
          EntryStart: entryFilters.Start,
          EntryEnd: entryFilters.End,
          EntryQuery: entryFilters.Query,
          EntrySort: entryFilters.Sort,
          EntryOrder: entryFilters.Order,
        }
      : {}),
  };
  // 汇总与子页分别加载；切换 tab 不清空汇总，也不重复计算汇总。
  const overviewParams = {
    Month: params.Month,
    Scope: scope,
    Current: tab === 'overview' ? page : 1,
    PageSize: 20,
    EntryKind: entryFilters.Kind,
    EntryStoreId: entryFilters.Store,
    EntryStart: entryFilters.Start,
    EntryEnd: entryFilters.End,
    EntryQuery: entryFilters.Query,
    EntrySort: entryFilters.Sort,
    EntryOrder: entryFilters.Order,
  };
  const contextKey = JSON.stringify([params.Month, scope, revision]);
  const requestKey = JSON.stringify([overviewParams, revision]);
  const tabKey = JSON.stringify([params, tab, revision]);
  const overview = loadedContext === contextKey ? loadedOverview : undefined;
  const rows = rowsKey === tabKey ? loadedRows : [];
  const refresh = () => setRevision((v) => v + 1);
  useEffect(() => {
    sessionStorage.setItem(`${preference}:scope`, scope);
    sessionStorage.setItem(`${preference}:month`, month.format('YYYY-MM'));
  }, [scope, month.format('YYYY-MM')]);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(false);
    settlementGet('overview', overviewParams)
      .then((a) => {
        if (cancelled) return;
        setLoadedContext(contextKey);
        setOverview(a.Data);
        setLoadedOverviewKey(requestKey);
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError(true);
          setOverview(undefined);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [requestKey]);
  useEffect(() => {
    // 资料变更或切换核算范围后丢弃旧缓存，避免继续显示旧财务结果。
    tabCache.current.clear();
  }, [month.format('YYYY-MM'), scope, revision]);
  useEffect(() => {
    let cancelled = false;
    setRowsError(false);
    if (tab === 'overview') {
      setRowsLoading(false);
      return;
    }
    const apply = (data: any) => {
      setRowsKey(tabKey);
      setRows(data.Items || []);
      setTotal(data.Total || 0);
      setProducts(data.Products || []);
    };
    const cached = tabCache.current.get(tabKey);
    if (cached) {
      apply(cached);
      setRowsLoading(false);
      return;
    }
    setRowsLoading(true);
    const path =
      tab === 'wallet' || tab === 'point'
        ? 'assets'
        : tab === 'rules'
        ? 'cost-rules'
        : tab;
    settlementGet(path, { ...params, Kind: tab })
      .then((r) => {
        if (cancelled) return;
        tabCache.current.set(tabKey, r.Data);
        apply(r.Data);
      })
      .catch(() => {
        if (!cancelled) setRowsError(true);
      })
      .finally(() => {
        if (!cancelled) setRowsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tabKey]);
  const command = async (path: string, data?: any) => {
    await settlementPost(path, data);
    message.success('已保存');
    refresh();
  };
  const edit = (value: any) => {
    setEditor(value);
    setCostFiles([]);
    setRemoveCostImage(false);
    form.resetFields();
    form.setFieldsValue(value.values || {});
  };
  const allocations = async (ref: string, current = 1) => {
    const r = await settlementGet('allocations', {
      ...params,
      Reference: ref,
      Current: current,
    });
    setDetail({
      title: `来源明细 · ${ref}`,
      reference: ref,
      page: current,
      total: r.Data.Total,
      rows: r.Data.Items,
      cost: r.Data.Expense,
    });
  };
  const selectedTotals = overview?.Totals || [];
  const net = selectedTotals
    .filter((x: any) => x.StoreId !== 0)
    .reduce((sum: number, x: any) => sum + x.amount, 0);
  const table = (columns: any[], data = rows, options: any = {}) => (
    <Table
      rowKey={(r: any) => r.id ?? r.key}
      loading={tab === 'overview' ? loading : rowsLoading}
      columns={columns.map((c) => ({
        ...c,
        title: metricLabel(c.title),
        onHeaderCell: () => ({ style: { whiteSpace: 'nowrap' } }),
      }))}
      dataSource={data}
      scroll={{ x: 'max-content' }}
      pagination={false}
      {...options}
    />
  );
  const entryColumns = [
    { title: '归账月份', dataIndex: 'month' },
    {
      title: '业务发生时间',
      dataIndex: 'event_at',
      sorter: true,
      sortOrder:
        entryFilters.Sort === 'event_at'
          ? entryFilters.Order === 'asc'
            ? 'ascend'
            : 'descend'
          : null,
    },
    ...(!entryFilters.Kind
      ? [
          {
            title: '项目',
            dataIndex: 'kind',
            render: (s: string) => kinds[s] || s,
          },
        ]
      : []),
    {
      title: '结算出款方',
      render: (_: any, r: any) =>
        r.amount < 0 ? r.receiver_name : r.payer_name,
    },
    {
      title: '结算收款方',
      render: (_: any, r: any) =>
        r.amount < 0 ? r.payer_name : r.receiver_name,
    },
    {
      title: '结算金额',
      dataIndex: 'amount',
      render: (v: number) => yuan(Math.abs(v)),
      sorter: true,
      sortOrder:
        entryFilters.Sort === 'amount'
          ? entryFilters.Order === 'asc'
            ? 'ascend'
            : 'descend'
          : null,
    },
    ...(['wallet', 'wallet_refund'].includes(entryFilters.Kind)
      ? [
          {
            title:
              entryFilters.Kind === 'wallet_refund' ? '退回金额' : '扣款金额',
            dataIndex: 'face_amount',
            render: (v: number | null) =>
              v === null || v === undefined ? '—' : yuan(Math.abs(v)),
            sorter: true,
            sortOrder:
              entryFilters.Sort === 'face_amount'
                ? entryFilters.Order === 'asc'
                  ? 'ascend'
                  : 'descend'
                : null,
          },
        ]
      : []),
    {
      title: '原始业务',
      dataIndex: 'reference',
      render: (ref: string, row: any) =>
        row.kind.startsWith('wallet') || row.kind === 'point_cost' ? (
          <Button type="link" onClick={() => allocations(ref)}>
            {ref}
          </Button>
        ) : (
          ref
        ),
    },
    {
      title: '操作',
      key: 'actions',
      fixed: 'right',
      width: 110,
      render: (_: any, r: any) => (
        <Button
          type="link"
          style={{ padding: 0 }}
          onClick={() => setEntryDetail(r)}
        >
          查看说明
        </Button>
      ),
    },
  ];
  const entryTableOptions = {
    onChange: (_: any, __: any, sorter: any) => {
      changeEntryFilters({
        Sort: sorter.order ? sorter.field : 'event_at',
        Order: sorter.order === 'ascend' ? 'asc' : 'desc',
      });
    },
  };
  const entryFilterControls = (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Space wrap>
        <Select
          aria-label="结算项目"
          style={{ minWidth: 190 }}
          value={entryFilters.Kind}
          options={[
            { value: '', label: '全部项目' },
            ...Object.entries(kinds)
              .filter(([key]) =>
                [
                  'wechat_play',
                  'wechat_catering',
                  'wechat_refund',
                  'wallet',
                  'wallet_refund',
                  'month_card',
                  'month_card_carry',
                  'point_cost',
                  'settlement_fee',
                ].includes(key),
              )
              .filter(([key]) => tab !== 'cash' || key.startsWith('wechat_'))
              .map(([value, label]) => ({ value, label })),
          ]}
          onChange={(Kind) =>
            changeEntryFilters({ Kind, Sort: 'event_at', Order: 'desc' })
          }
        />
        <Select
          aria-label="涉及门店"
          placeholder="全部涉及门店"
          allowClear
          style={{ minWidth: 170 }}
          value={entryFilters.Store}
          options={[
            { value: 0, label: '总部' },
            ...(initialState?.auth?.Stores || []).map((store) => ({
              value: store.Id,
              label: store.Name,
            })),
          ]}
          onChange={(Store) => changeEntryFilters({ Store })}
        />
        <DatePicker.RangePicker
          aria-label="业务发生日期"
          value={
            entryFilters.Start && entryFilters.End
              ? [dayjs(entryFilters.Start), dayjs(entryFilters.End)]
              : null
          }
          onChange={(dates) =>
            changeEntryFilters({
              Start: dates?.[0]?.format('YYYY-MM-DD') || '',
              End: dates?.[1]?.format('YYYY-MM-DD') || '',
            })
          }
        />
        <Input.Search
          aria-label="原始业务查询"
          placeholder="查询原始业务编号"
          style={{ width: 230 }}
          allowClear
          enterButton="查询"
          value={entrySearch}
          onChange={(event) => setEntrySearch(event.target.value)}
          onSearch={(Query) => changeEntryFilters({ Query: Query.trim() })}
        />
        <Button
          onClick={() => {
            setEntrySearch('');
            changeEntryFilters({
              Kind: '',
              Store: undefined,
              Start: '',
              End: '',
              Query: '',
              Sort: 'event_at',
              Order: 'desc',
            });
          }}
        >
          重置筛选
        </Button>
      </Space>
      <Typography.Text type="secondary">
        筛选与排序覆盖全部明细。点击日期或金额列可排序；全月汇总和导出报表不受筛选影响。
      </Typography.Text>
    </Space>
  );
  return (
    <PageContainer
      title="门店结算"
      subTitle="自然月统一结算 · 每笔金额均可追溯"
    >
      <Space wrap style={{ marginBottom: 24 }}>
        {[
          <DatePicker
            key="month"
            picker="month"
            value={month}
            allowClear={false}
            disabledDate={(date) =>
              !date.isBefore(beijingMonth, 'month') ||
              (!!loadedOverview?.FirstSettlementMonth &&
                date.format('YYYY-MM') < loadedOverview.FirstSettlementMonth)
            }
            onChange={(v) => {
              if (v) {
                setMonth(v);
                setPage(1);
              }
            }}
          />,
          ...(hq
            ? [
                <Radio.Group
                  key="scope"
                  value={scope}
                  onChange={(e) => {
                    setScope(e.target.value);
                    setPage(1);
                  }}
                  optionType="button"
                  options={[
                    { label: '当前门店', value: 'store' },
                    { label: '总部汇总', value: 'all' },
                  ]}
                />,
              ]
            : []),
          ...(scope === 'store'
            ? [<StoreSwitcher key="store" label="查看门店" />]
            : []),
          <div key="settlement-actions" ref={setActionContainer} />,
          <Button
            key="export"
            disabled={!overview?.Report}
            onClick={async () => {
              const blob = await settlementExport({
                ...params,
                ReportId: overview?.Report?.Id,
              });
              const url = URL.createObjectURL(blob);
              const link = document.createElement('a');
              link.href = url;
              link.download = `结算报表-${overview?.Report?.Number}.csv`;
              link.click();
              setTimeout(() => URL.revokeObjectURL(url), 1000);
            }}
          >
            导出当前版本报表
          </Button>,
          <Button key="refresh" onClick={refresh}>
            刷新
          </Button>,
        ]}
      </Space>
      {loadError ? (
        <Alert
          showIcon
          type="error"
          message="结算数据加载失败"
          description="请刷新重试；当前未展示汇总，避免将失败误认为零金额。"
        />
      ) : overview?.Enabled === false ? (
        <Alert
          showIcon
          type="info"
          message="结算尚未启用"
          description={overview.Message}
        />
      ) : !overview ? (
        <Card loading />
      ) : (
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Card
            title={`月度结算 · ${month
              .startOf('month')
              .format('YYYY-MM-DD')} 至 ${month
              .endOf('month')
              .format('YYYY-MM-DD')}（北京时间）`}
          >
            {overview.PartialOpeningPeriod && (
              <Alert
                showIcon
                type="info"
                style={{ marginBottom: 16 }}
                message={`首次月结仅包含 ${dayjs(overview.CoverageStart).format(
                  'YYYY-MM-DD HH:mm:ss',
                )} 起的业务（北京时间）`}
                description="切换前的历史流水不补结算；旧储值、积分以切换时剩余资产继续使用，旧月卡只分配剩余卡期金额。"
              />
            )}
            <ReportActions
              key={month.format('YYYY-MM') + scope}
              month={month.format('YYYY-MM')}
              overview={overview}
              actionContainer={actionContainer}
              headquarters={hq}
              allStores={scope === 'all'}
              selectAllStores={() => {
                setScope('all');
                setPage(1);
              }}
              ended={month.isBefore(beijingMonth, 'month')}
              refresh={refresh}
            />
          </Card>
          {!overview.Report && (
            <Alert
              showIcon
              type="info"
              message="尚未生成结算报表"
              description="先在下方补齐核销及积分成本资料，再生成报表。生成后即可核对完整金额和明细，确认前不会正式入账。微信消费与退款、资产来源查询不执行结算。"
            />
          )}
          {overview.Report &&
            (!overview.CashIncluded || !overview.FeesIncluded) && (
              <Alert
                showIcon
                type="warning"
                message="这是尚未采用完整统一结算口径的旧版报表"
                description="旧报表金额保持不变。尚未开始收付款的待确认报表，请作废后重新生成；已经收付款的差异请联系总部核对处理。"
              />
            )}
          {overview.Report && (
            <Row gutter={[16, 16]}>
              <Col xs={24} md={8}>
                <Card>
                  <Statistic
                    title={metricLabel(
                      `${month.format('YYYY-MM')} · ${
                        overview.Report
                          ? overview.FeesIncluded
                            ? '扣费后结算净额'
                            : '原报表结算净额'
                          : '当前记录净额（非完整月报）'
                      }`,
                    )}
                    value={net / 100}
                    precision={2}
                    prefix="¥"
                  />
                  <Typography.Text type="secondary">
                    收款及分配 − 退款和承担费用；负数表示应向总部缴回
                  </Typography.Text>
                </Card>
              </Col>
              <Col xs={24} md={8}>
                <Card>
                  <Statistic
                    title={metricLabel('结算记录')}
                    value={overview?.EntryCount || 0}
                  />
                  <Tag
                    color={
                      ['locked', 'confirmed'].includes(overview?.Status)
                        ? 'green'
                        : 'blue'
                    }
                  >
                    {states[overview?.Status] || '待核对'}
                  </Tag>
                </Card>
              </Col>
              <Col xs={24} md={8}>
                <Card>
                  <Typography.Text>
                    每个自然月单独出具固定版本报表。负数须当期转回总部，不结转抵扣。
                  </Typography.Text>
                </Card>
              </Col>
            </Row>
          )}
          {overview.Report && (
            <Card title={metricLabel('统一结算手续费 · 0.6%')}>
              <Typography.Paragraph type="secondary">
                微信消费净额、储值本金净额、线上月卡分配按门店汇总后计费，四舍五入到分。
                积分成本与补偿不计费；退款冲减基数，负手续费表示冲回。
                这是内部结算扣费口径，生成报表时固定。
              </Typography.Paragraph>
              {overview.FeesIncluded ? (
                table(
                  [
                    { title: '门店', dataIndex: 'StoreName' },
                    {
                      title: '扣费前净额',
                      render: (_: any, r: any) => yuan(r.amount + r.Fee),
                    },
                    { title: '计费基数', dataIndex: 'Base', render: yuan },
                    { title: '费率', render: () => '0.6%' },
                    {
                      title: '手续费（正数扣减 / 负数冲回）',
                      dataIndex: 'Fee',
                      render: yuan,
                    },
                    {
                      title: '扣费后应收 / 应付',
                      dataIndex: 'amount',
                      render: yuan,
                    },
                  ],
                  (overview.Fees || []).map((fee: any) => ({
                    ...selectedTotals.find(
                      (t: any) => t.StoreId === fee.StoreId,
                    ),
                    ...fee,
                    id: fee.StoreId,
                  })),
                )
              ) : (
                <Typography.Text type="secondary">
                  {overview.Report
                    ? '旧报表金额保留不变，未计算此手续费。'
                    : '生成月报后展示各门店的计费基数、手续费和扣费后净额。'}
                </Typography.Text>
              )}
            </Card>
          )}

          <Tabs
            activeKey={tab}
            onChange={(v) => {
              setTab(v);
              setEntryFilters((old) => ({
                ...old,
                Kind: '',
                Sort: 'event_at',
                Order: 'desc',
              }));
              setPage(1);
            }}
            items={[
              { key: 'overview', label: '月度结算' },
              { key: 'cash', label: '微信消费与退款' },
              { key: 'wallet', label: '储值批次' },
              { key: 'cards', label: '月卡分配池' },
              { key: 'point', label: '积分来源' },
              { key: 'expenses', label: '积分成本' },
              ...(hq ? [{ key: 'rules', label: '价格与成本设置' }] : []),
            ]}
          />
          {rowsError && tab !== 'overview' && (
            <Alert
              type="error"
              showIcon
              message="当前明细加载失败"
              description="请点击刷新重试；此错误不影响已加载的报表汇总。"
            />
          )}
          {tab === 'overview' && overview.Report && (
            <>
              {table(
                [
                  { title: '门店', dataIndex: 'StoreName' },
                  ...[
                    ['wechat_play', '游玩微信收款'],
                    ['wechat_catering', '餐饮微信收款'],
                    ['wechat_refund', '微信退款'],
                    ['wallet', '储值本金净额'],
                    ['month_card', '月卡分配'],
                    ['point_compensation', '积分成本补偿'],
                    ['point_cost', '积分承担成本'],
                    ['settlement_fee', '手续费对净额的影响'],
                  ].map(([key, title]) => ({
                    title,
                    render: (_: any, r: any) =>
                      yuan(overview.Breakdown?.[r.StoreId]?.[key] || 0),
                  })),
                  { title: '收益及补偿', dataIndex: 'income', render: yuan },
                  { title: '承担金额', dataIndex: 'deduction', render: yuan },
                  { title: '净额', dataIndex: 'amount', render: yuan },
                ],
                selectedTotals.map((x: any) => ({ ...x, id: x.StoreId })),
              )}
              <Typography.Title level={5}>
                结算明细（筛选后{' '}
                {loading
                  ? '…'
                  : overview?.FilteredEntryCount ??
                    overview?.EntryCount ??
                    0}{' '}
                笔 / 全月 {overview?.EntryCount || 0} 笔）
              </Typography.Title>
              {entryFilterControls}
              {table(
                entryColumns,
                loadedOverviewKey === requestKey ? overview?.Entries || [] : [],
                entryTableOptions,
              )}
              <Typography.Title level={5}>已确认结算记录</Typography.Title>
              {table(
                [
                  { title: '门店', dataIndex: 'store_id', render: storeName },
                  {
                    title: '应付 / 应收净额',
                    dataIndex: 'amount',
                    render: yuan,
                  },
                  { title: '处理时间', dataIndex: 'paid_at' },
                  { title: '付款 / 收款凭证', dataIndex: 'payment_ref' },
                ],
                overview?.Statements || [],
              )}
            </>
          )}
          {tab === 'cash' && (
            <>
              <Alert
                showIcon
                type="info"
                message="普通微信消费及成功退款"
                description="支付和退款分别按成功时间归月，混合支付只列微信部分；充值、购卡和组局意向金不重复计入本栏。报表生成后显示固定版本的明细。"
              />
              {entryFilterControls}
              {table(entryColumns, rows, entryTableOptions)}
            </>
          )}
          {(tab === 'wallet' || tab === 'point') && (
            <>
              <Alert
                type="info"
                message={
                  tab === 'wallet'
                    ? `${month.format(
                        'YYYY-MM',
                      )} 储值批次 · 共 ${total} 个 · 资金由总部保管`
                    : `共 ${total} 个积分来源批次`
                }
                description={
                  tab === 'wallet'
                    ? '本月消费额为本次结算月的消费扣款，退款另列在金额下方；本月结算额已扣除退款本金，不含手续费。剩余金额为当前实时余额，并非所选月末快照。已生成报表时，本月金额采用该报表明细。'
                    : '积分成本按发放时确定的责任方承担，历史积分归南山。'
                }
              />
              {table([
                { title: '批次', dataIndex: 'id' },
                { title: '用户', dataIndex: 'user_name' },
                { title: '来源', dataIndex: 'source_key', render: sourceName },
                ...(tab === 'wallet'
                  ? [
                      {
                        title: '原始余额',
                        dataIndex: 'face_total',
                        render: yuan,
                      },
                      {
                        title: '原始结算额',
                        dataIndex: 'principal_total',
                        render: yuan,
                      },
                      {
                        title: '本月消费额',
                        dataIndex: 'month_consumption',
                        render: (v: number, r: any) => (
                          <Space direction="vertical" size={0}>
                            <span>{yuan(v)}</span>
                            {!!r.month_refund && (
                              <Typography.Text type="secondary">
                                退款 {yuan(r.month_refund)}
                              </Typography.Text>
                            )}
                          </Space>
                        ),
                      },
                      {
                        title: '本月结算额',
                        dataIndex: 'month_settlement',
                        render: (v: number, r: any) => (
                          <Space direction="vertical" size={0}>
                            <span>{yuan(v)}</span>
                            {!!r.month_refund_principal && (
                              <Typography.Text type="secondary">
                                已扣退款本金 {yuan(r.month_refund_principal)}
                              </Typography.Text>
                            )}
                          </Space>
                        ),
                      },
                      {
                        title: '剩余余额',
                        dataIndex: 'remaining',
                        render: (v: number, r: any) => (
                          <Space direction="vertical" size={0}>
                            <span>{yuan(v)}</span>
                            {!!r.frozen && (
                              <Typography.Text type="secondary">
                                其中冻结 {yuan(r.frozen)}
                              </Typography.Text>
                            )}
                          </Space>
                        ),
                      },
                      {
                        title: '剩余结算额',
                        dataIndex: 'principal_remaining',
                        render: yuan,
                      },
                    ]
                  : [
                      {
                        title: '承担方',
                        dataIndex: 'responsible_store_id',
                        render: storeName,
                      },
                      { title: '原始积分', dataIndex: 'face_total' },
                      { title: '剩余积分', dataIndex: 'remaining' },
                    ]),
              ])}
            </>
          )}
          {tab === 'cards' && (
            <>
              <Alert
                showIcon
                message="每期金额按卡期与自然月的交集释放，再按当月有效游玩时长分店。"
                description={
                  overview.Report
                    ? '下表采用本版报表快照，包含本次分配及到期补分；待确认时即可核对，确认后才正式入账。无核销月份暂留，到期补分；整卡零使用归总部。'
                    : '下表为核销与卡期资料，分配结果以生成的报表为准；确认前不会正式入账。'
                }
              />
              {table([
                { title: '卡池', dataIndex: 'id' },
                { title: '用户', dataIndex: 'user_name' },
                { title: '原开卡单', dataIndex: 'order_id' },
                { title: '开卡渠道', dataIndex: 'source_text' },
                {
                  title: '卡期',
                  render: (_: any, r: any) => (
                    <span>
                      {r.starts_at}
                      <br />
                      {r.ends_at}
                    </span>
                  ),
                },
                { title: '总金额', dataIndex: 'amount', render: yuan },
                {
                  title: '本月可分配',
                  dataIndex: 'released_amount',
                  render: yuan,
                },
                {
                  title: '本月实际分配',
                  render: (_: any, r: any) =>
                    yuan(
                      r.periods?.find(
                        (p: any) => p.month === month.format('YYYY-MM'),
                      )?.allocated_amount ?? 0,
                    ),
                },
                {
                  title: '累计实际分配',
                  dataIndex: 'distributed_total',
                  render: yuan,
                },
                {
                  title: '剩余待分配',
                  render: (_: any, r: any) =>
                    yuan(r.amount - r.distributed_total),
                },
                {
                  title: '操作',
                  fixed: 'right',
                  width: 148,
                  render: (_: any, r: any) => (
                    <Button
                      type="link"
                      onClick={() =>
                        setDetail({
                          title: `月卡 #${r.id} · ${month.format(
                            'YYYY-MM',
                          )} 分配`,
                          card: r,
                        })
                      }
                    >
                      查看分配明细
                    </Button>
                  ),
                },
              ])}
            </>
          )}
          {tab === 'expenses' &&
            table([
              {
                title: '成本单',
                dataIndex: 'expense_key',
                render: (s: string) => (
                  <Button type="link" onClick={() => allocations(s)}>
                    {s}
                  </Button>
                ),
              },
              { title: '商品 / 活动', dataIndex: 'source_name' },
              {
                title: '类型',
                dataIndex: 'kind',
                render: (s: string) => kinds[s],
              },
              { title: '成本', dataIndex: 'amount', render: yuan },
              {
                title: '商品提供方',
                dataIndex: 'provider_id',
                render: storeName,
              },
              { title: '履约时间', dataIndex: 'completed_at' },
              {
                title: '状态',
                dataIndex: 'status',
                render: (s: string, r: any) => (
                  <Tag color={s === 'needs_cost' ? 'orange' : 'blue'}>
                    {r.report_status
                      ? r.report_status === 'draft'
                        ? '已纳入报表，待确认'
                        : '已结算'
                      : states[s]}
                  </Tag>
                ),
              },
              { title: '文字备注', dataIndex: 'note' },
              {
                title: '付款凭证图片',
                render: (_: any, r: any) =>
                  r.has_image ? (
                    <ReceiptProof id={r.id} kind="expenses" />
                  ) : (
                    '未上传'
                  ),
              },
              {
                title: '操作',
                render: (_: any, r: any) =>
                  hq &&
                  !r.report_status &&
                  ['needs_cost', 'ready', 'pending'].includes(r.status) ? (
                    <Button
                      onClick={() =>
                        edit({
                          type: 'cost',
                          id: r.id,
                          completed: !!r.completed_at,
                          has_image: r.has_image,
                          values: {
                            ProviderId: r.provider_id,
                            Amount:
                              r.amount === null || r.amount === undefined
                                ? undefined
                                : r.amount / 100,
                            Note: r.note,
                          },
                        })
                      }
                    >
                      {r.completed_at
                        ? '补充 / 修改结算资料'
                        : '修改预估结算价'}
                    </Button>
                  ) : null,
              },
            ])}
          {tab === 'rules' && (
            <>
              <CardPricing />
              <Alert
                type="info"
                message="商品配置单件预估结算价；抽奖配置整场奖品预估总价，均可选填。新规则只影响后续成本单；已生成成本单可在入账前单独修改、补充，所有已履约成本均须总部补齐资料后才能生成报表；生成后修改资料需先作废报表。"
              />
              <Button
                onClick={() =>
                  edit({
                    type: 'rule',
                    values: {
                      RuleType: 'product',
                      SourceId: undefined,
                      Amount: undefined,
                      Note: '',
                    },
                  })
                }
              >
                新增 / 更新成本标准
              </Button>
              {table([
                {
                  title: '成本对象',
                  dataIndex: 'key',
                  render: (key: string) =>
                    key.startsWith('product:')
                      ? products.find((p) => String(p.id) === key.split(':')[1])
                          ?.name || `积分商品 #${key.split(':')[1]}`
                      : `抽奖活动 #${key.split(':')[1]}`,
                },
                { title: '成本', dataIndex: 'amount', render: yuan },
                { title: '依据', dataIndex: 'note' },
                { title: '更新时间', dataIndex: 'updated_at' },
              ])}
            </>
          )}
          {tab !== 'rules' && (tab !== 'overview' || overview.Report) && (
            <Pagination
              current={page}
              pageSize={20}
              total={
                tab === 'overview'
                  ? overview.Report
                    ? overview.FilteredEntryCount ?? overview.EntryCount ?? 0
                    : 0
                  : rowsKey === tabKey
                  ? total
                  : 0
              }
              onChange={setPage}
              showSizeChanger={false}
              showTotal={(n) => `共 ${n} 条，已分页完整提供`}
            />
          )}
        </Space>
      )}
      <Modal
        title="结算说明"
        open={!!entryDetail}
        onCancel={() => setEntryDetail(undefined)}
        footer={null}
        destroyOnClose
      >
        {entryDetail && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Typography.Text>
              {kinds[entryDetail.kind] || entryDetail.kind} ·{' '}
              {entryDetail.month}
            </Typography.Text>
            <Typography.Text>
              {entryDetail.amount < 0
                ? entryDetail.receiver_name
                : entryDetail.payer_name}
              {' → '}
              {entryDetail.amount < 0
                ? entryDetail.payer_name
                : entryDetail.receiver_name}
              {' · '}
              {yuan(Math.abs(entryDetail.amount))}
            </Typography.Text>
            <Typography.Text type="secondary">
              这里表示结算归属关系，实际收付款以整月结算净额为准。
            </Typography.Text>
            <Typography.Text>
              业务发生时间：{entryDetail.event_at}
            </Typography.Text>
            <Typography.Text>原始业务：{entryDetail.reference}</Typography.Text>
            <Typography.Title level={5}>计算说明</Typography.Title>
            <Typography.Paragraph style={{ whiteSpace: 'pre-wrap' }}>
              {entryDetail.detail || '无补充说明'}
            </Typography.Paragraph>
          </Space>
        )}
      </Modal>
      <Modal
        title={
          {
            paid: '登记实际付款 / 收款凭证',
            usage: '核验月卡有效时长',
            rule: '设置成本标准',
            cost: '确认结算成本',
          }[editor?.type as string] || '结算操作'
        }
        okText={
          editor?.type === 'cost'
            ? editor.completed
              ? '保存结算资料'
              : '保存预估价'
            : '确定'
        }
        open={!!editor}
        onCancel={() => {
          if (!savingEditor) setEditor(undefined);
        }}
        confirmLoading={savingEditor}
        closable={!savingEditor}
        maskClosable={!savingEditor}
        cancelButtonProps={{ disabled: savingEditor }}
        destroyOnClose
        onOk={async () => {
          const v = await form.validateFields();
          const data = {
            ...v,
            Key: editor.type === 'rule' ? `${v.RuleType}:${v.SourceId}` : v.Key,
            Amount:
              v.Amount === null || v.Amount === undefined
                ? undefined
                : Math.round(v.Amount * 100),
          };
          const path =
            editor.type === 'usage'
              ? `usages/${editor.id}/review`
              : editor.type === 'paid'
              ? `statements/${editor.id}/paid`
              : editor.type === 'rule'
              ? 'cost-rules'
              : `expenses/${editor.id}/confirm`;
          setSavingEditor(true);
          try {
            if (editor.type === 'cost') {
              const body = new FormData();
              body.append('Amount', String(data.Amount));
              body.append('ProviderId', String(v.ProviderId));
              body.append('Note', v.Note || '');
              body.append(
                'RemoveImage',
                String(removeCostImage && costFiles.length === 0),
              );
              const file = costFiles[0]?.originFileObj;
              if (file) body.append('File', file);
              await command(path, body);
            } else {
              await command(path, data);
            }
            setEditor(undefined);
            if (editor.type === 'usage') setDetail(undefined);
          } finally {
            setSavingEditor(false);
          }
        }}
      >
        <Form
          form={form}
          layout="vertical"
          preserve={false}
          disabled={savingEditor}
        >
          {editor?.type === 'cost' && (
            <Alert
              style={{ marginBottom: 16 }}
              type="info"
              showIcon
              message={
                editor.completed
                  ? '保存金额、提供方及选填的备注、付款凭证；生成报表不入账，最终确认结算时才固定分摊。'
                  : '尚未履约，仅保存预估价；提货或开奖完成后仍需总部确认。'
              }
              description="本次只修改这张成本单，不改变商品或抽奖的后续价格设置；金额和提供方的修改会留痕。"
            />
          )}
          {editor?.type === 'usage' ? (
            <>
              <Form.Item
                name="Seconds"
                label="有效时长（秒；0 表示不参与）"
                rules={[{ required: true }]}
              >
                <InputNumber min={0} max={editor.max} precision={0} />
              </Form.Item>
              <Form.Item
                name="Note"
                label="核验依据"
                rules={[{ required: true }]}
              >
                <Input.TextArea maxLength={500} />
              </Form.Item>
            </>
          ) : editor?.type === 'paid' ? (
            <Form.Item
              name="PaymentRef"
              label="银行回单 / 收款凭证号"
              rules={[{ required: true }]}
            >
              <Input maxLength={200} />
            </Form.Item>
          ) : (
            <>
              {editor?.type === 'rule' && (
                <>
                  <Form.Item
                    name="RuleType"
                    label="成本类型"
                    rules={[{ required: true }]}
                  >
                    <Radio.Group
                      options={[
                        { label: '积分兑换商品（单件）', value: 'product' },
                        { label: '积分抽奖（整场）', value: 'raffle' },
                      ]}
                    />
                  </Form.Item>
                  <Form.Item noStyle shouldUpdate>
                    {({ getFieldValue }) => (
                      <Form.Item
                        name="SourceId"
                        label={
                          getFieldValue('RuleType') === 'product'
                            ? '兑换商品'
                            : '抽奖活动编号'
                        }
                        rules={[{ required: true }]}
                      >
                        {getFieldValue('RuleType') === 'product' ? (
                          <Select
                            showSearch
                            optionFilterProp="label"
                            options={products.map((p) => ({
                              value: p.id,
                              label: `${p.name}（#${p.id}）`,
                            }))}
                          />
                        ) : (
                          <InputNumber min={1} precision={0} />
                        )}
                      </Form.Item>
                    )}
                  </Form.Item>
                </>
              )}
              <Form.Item
                name="Amount"
                label="实际结算成本（元）"
                rules={[{ required: true }]}
              >
                <InputNumber min={0} max={1000000} precision={2} />
              </Form.Item>
              {editor?.type === 'cost' && (
                <Form.Item
                  name="ProviderId"
                  label="实际提供商品的一方"
                  rules={[{ required: true }]}
                >
                  <Select
                    options={[
                      { value: 0, label: '总部' },
                      ...(initialState?.auth?.Stores || []).map((s) => ({
                        value: s.Id,
                        label: s.Name,
                      })),
                    ]}
                  />
                </Form.Item>
              )}
              <Form.Item
                name="Note"
                label={
                  editor?.type === 'cost'
                    ? '文字备注（选填）'
                    : '成本依据 / 确认说明'
                }
                rules={editor?.type === 'cost' ? [] : [{ required: true }]}
              >
                <Input.TextArea maxLength={500} rows={3} />
              </Form.Item>
              {editor?.type === 'cost' && (
                <Form.Item
                  label="付款凭证图片（选填）"
                  extra="支持一张 JPG / PNG 图片，最大 5MB。"
                >
                  {editor.has_image && !removeCostImage && (
                    <Space>
                      <ReceiptProof id={editor.id} kind="expenses" />
                      <Button
                        danger
                        type="link"
                        onClick={() => setRemoveCostImage(true)}
                      >
                        移除原图片
                      </Button>
                    </Space>
                  )}
                  {editor.has_image && removeCostImage && (
                    <Button
                      type="link"
                      onClick={() => setRemoveCostImage(false)}
                    >
                      保留原图片
                    </Button>
                  )}
                  <Upload
                    accept="image/jpeg,image/png"
                    maxCount={1}
                    fileList={costFiles}
                    disabled={savingEditor}
                    beforeUpload={(file) => {
                      if (
                        !['image/jpeg', 'image/png'].includes(file.type) ||
                        file.size > 5 * 1024 * 1024
                      ) {
                        message.error('请选择 5MB 以内的 JPG 或 PNG 图片');
                        return Upload.LIST_IGNORE;
                      }
                      return false;
                    }}
                    onChange={({ fileList }) => setCostFiles(fileList)}
                  >
                    <Button>
                      {editor.has_image ? '选择替换图片' : '选择图片'}
                    </Button>
                  </Upload>
                </Form.Item>
              )}
            </>
          )}
        </Form>
      </Modal>
      <Drawer
        title={detail?.title}
        width={1000}
        open={!!detail}
        onClose={() => setDetail(undefined)}
      >
        {detail?.cost && (
          <Space
            direction="vertical"
            style={{ width: '100%', marginBottom: 24 }}
          >
            <Alert
              type="info"
              message={`本次实际成本：${yuan(
                detail.cost.amount,
              )}；商品提供方：${storeName(detail.cost.provider_id)}${
                detail.cost.report_status === 'draft'
                  ? '；本版报表待确认'
                  : detail.cost.report_status === 'confirmed'
                  ? '；已结算'
                  : ''
              }`}
              description="按实际消耗积分的来源占比分担成本；提供商品的一方获得成本补偿，其自身责任部分在净额中抵销。"
            />
            {table(
              [
                {
                  title: '积分责任方',
                  dataIndex: 'store_id',
                  render: storeName,
                },
                { title: '消耗积分', dataIndex: 'points' },
                {
                  title: '责任占比',
                  render: (_: any, r: any) =>
                    detail.cost.total_points
                      ? `${(
                          (r.points / detail.cost.total_points) *
                          100
                        ).toFixed(2)}%`
                      : '—',
                },
                { title: '承担成本', dataIndex: 'amount', render: yuan },
              ],
              detail.cost.shares.map((x: any) => ({ ...x, id: x.store_id })),
            )}
            <Typography.Title level={5}>逐笔来源</Typography.Title>
          </Space>
        )}
        {detail?.rows && (
          <>
            {table(
              [
                { title: '批次', dataIndex: 'batch_id' },
                {
                  title: '来源单',
                  dataIndex: 'source_key',
                  render: sourceName,
                },
                {
                  title: '原始本金',
                  dataIndex: 'principal_total',
                  render: (v: number, r: any) =>
                    r.kind === 'wallet' ? yuan(v) : '—',
                },
                {
                  title: '原始余额 / 积分',
                  dataIndex: 'face_total',
                  render: (v: number, r: any) =>
                    r.kind === 'wallet' ? yuan(v) : `${v} 积分`,
                },
                {
                  title: '本次余额 / 积分',
                  dataIndex: 'amount',
                  render: (v: number, r: any) =>
                    r.kind === 'wallet' ? yuan(v) : `${v} 积分`,
                },
                {
                  title: '折算本金',
                  dataIndex: 'principal',
                  render: (v: number, r: any) =>
                    r.kind === 'wallet' ? yuan(v) : '—',
                },
                {
                  title: '承担方',
                  dataIndex: 'responsible_store_id',
                  render: storeName,
                },
                {
                  title: '状态',
                  dataIndex: 'state',
                  render: (v: string) => states[v] || v,
                },
              ],
              detail.rows,
            )}
            <Pagination
              style={{ marginTop: 16 }}
              current={detail.page}
              pageSize={20}
              total={detail.total}
              showSizeChanger={false}
              showTotal={(n) => `共 ${n} 条来源`}
              onChange={(v) => allocations(detail.reference, v)}
            />
          </>
        )}
        {detail?.card && (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Alert
              showIcon
              message={`${detail.card.month} · ${
                states[detail.card.period_status]
              }`}
              description={`卡期金额 ${yuan(
                detail.card.amount,
              )}；所选月释放 ${yuan(
                detail.card.released_amount,
              )}。当月有效时长 ${(detail.card.total_seconds / 3600).toFixed(
                2,
              )} 小时。按秒计算占比并分配到分；以下门店明细仅展示权限范围内数据。`}
            />
            <Typography.Title level={5}>所选月时长分配</Typography.Title>
            {table(
              [
                { title: '门店', dataIndex: 'store_id', render: storeName },
                { title: '当月有效时长（秒）', dataIndex: 'seconds' },
                {
                  title: '时长占比',
                  width: 200,
                  render: (_: any, r: any) => (
                    <Progress
                      percent={
                        detail.card.total_seconds
                          ? Math.round(
                              (r.seconds / detail.card.total_seconds) * 10000,
                            ) / 100
                          : 0
                      }
                      size="small"
                    />
                  ),
                },
                { title: '当月分配金额', dataIndex: 'amount', render: yuan },
              ],
              detail.card.estimated.map((x: any) => ({ ...x, id: x.store_id })),
            )}
            {!!detail.card.carry_shares.length && (
              <>
                <Typography.Title level={5}>到期月暂留款补分</Typography.Title>
                {table(
                  [
                    { title: '门店', dataIndex: 'store_id', render: storeName },
                    { title: '全卡期有效时长（秒）', dataIndex: 'seconds' },
                    { title: '补分金额', dataIndex: 'amount', render: yuan },
                  ],
                  detail.card.carry_shares.map((x: any) => ({
                    ...x,
                    id: x.store_id,
                  })),
                )}
              </>
            )}
            <Typography.Title level={5}>
              {detail.card.report_status
                ? '逐月分配明细（含本版报表）'
                : '已确认的逐月分配'}
            </Typography.Title>
            {table(
              [
                { title: '月份', dataIndex: 'month' },
                { title: '本月释放', dataIndex: 'amount', render: yuan },
                {
                  title: '本月分配（含补分）',
                  dataIndex: 'allocated_amount',
                  render: yuan,
                },
                {
                  title: '其中暂留款补分',
                  dataIndex: 'carry_amount',
                  render: yuan,
                },
                {
                  title: '可见门店分配',
                  render: (_: any, r: any) =>
                    [...r.shares, ...r.carry_shares].map(
                      (x: any, i: number) => (
                        <div key={i}>
                          {storeName(x.store_id)}：{yuan(x.amount)}
                        </div>
                      ),
                    ),
                },
                { title: '生成时间', dataIndex: 'settled_at' },
              ],
              detail.card.periods,
            )}
            <Typography.Title level={5}>
              原始核销记录（完整卡期）
            </Typography.Title>
            {table(
              [
                { title: '游玩单', dataIndex: 'play_order_id' },
                { title: '门店', dataIndex: 'store_id', render: storeName },
                { title: '开始', dataIndex: 'started_at' },
                { title: '结束', dataIndex: 'ended_at' },
                { title: '秒数', dataIndex: 'seconds' },
                {
                  title: '状态',
                  dataIndex: 'status',
                  render: (s: string) => states[s],
                },
                { title: '备注', dataIndex: 'note' },
                {
                  title: '核验',
                  render: (_: any, r: any) =>
                    hq && r.status === 'review' ? (
                      <Button
                        onClick={() =>
                          edit({
                            type: 'usage',
                            id: r.id,
                            max: r.seconds,
                            values: { Seconds: r.seconds, Note: '' },
                          })
                        }
                      >
                        核验时长
                      </Button>
                    ) : null,
                },
              ],
              detail.card.uses,
            )}
          </Space>
        )}
      </Drawer>
    </PageContainer>
  );
}
