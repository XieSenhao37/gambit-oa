import { Table } from '@/components/AdaptiveTable';
import InteractiveChart from '@/components/InteractiveChart';
import StoreSwitcher from '@/components/StoreSwitcher';
import {
  getCateringOverview,
  getCouponOverview,
  getMembershipOverview,
  getOpsOverview,
  getPlayOverview,
  getPointOverview,
  getReferralOverview,
  getUserInsights,
  getUserOverview,
  getWalletOverview,
} from '@/services/stats';
import { ReloadOutlined } from '@ant-design/icons';
import { PageContainer } from '@ant-design/pro-components';
import {
  Alert,
  Card,
  Col,
  DatePicker,
  Empty,
  message,
  Radio,
  Row,
  Alert as ScopeAlert,
  Space,
  Spin,
  Statistic,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import dayjs, { Dayjs } from 'dayjs';
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactElement,
  type ReactNode,
} from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const { RangePicker } = DatePicker;
const { Text } = Typography;

// 品牌蓝为主的配色，辅以少量蓝色阶，避免破坏蓝黑白主识别
const BRAND_BLUE = '#1F4DFF';
const PIE_COLORS = [
  '#1F4DFF',
  '#4D79FF',
  '#7FA0FF',
  '#A9C0FF',
  '#0A1F66',
  '#11132B',
  '#6E7CB8',
];

const OPS_SERIES = [
  { key: 'Revenue', name: '总营收', color: BRAND_BLUE, axis: 'left' },
  { key: 'PlayRevenue', name: '桌游营收', color: '#11132B', axis: 'left' },
  { key: 'CateringRevenue', name: '饮品营收', color: '#7FA0FF', axis: 'left' },
  { key: 'OrderCount', name: '订单数', color: '#FA8C16', axis: 'right' },
  { key: 'NewUsers', name: '新增用户', color: '#6E7CB8', axis: 'right' },
] as const;

type RangePreset = 'today' | 'yesterday' | '7d' | '30d' | 'custom';
type Granularity = 'day' | 'week' | 'month';
type DashboardTabKey =
  | 'overview'
  | 'promotion'
  | 'user'
  | 'catering'
  | 'play'
  | 'asset';

const storeScopedDashboardTabs = new Set<DashboardTabKey>([
  'overview',
  'promotion',
  'catering',
  'play',
]);

interface DashboardData {
  ops?: API.OpsOverview;
  catering?: API.CateringOverview;
  play?: API.PlayOverview;
  user?: API.UserOverview;
  coupon?: API.CouponOverview;
  referral?: API.ReferralOverview;
  membership?: API.MembershipOverview;
  wallet?: API.WalletOverview;
  point?: API.PointOverview;
  insights?: API.UserInsights;
}

const presetToRange = (
  preset: Exclude<RangePreset, 'custom'>,
): [Dayjs, Dayjs] => {
  const end = dayjs();
  if (preset === 'yesterday') {
    const yesterday = end.subtract(1, 'day');
    return [yesterday.startOf('day'), yesterday.endOf('day')];
  }
  if (preset === 'today') return [dayjs().startOf('day'), end];
  if (preset === '7d') return [dayjs().subtract(6, 'day').startOf('day'), end];
  return [dayjs().subtract(29, 'day').startOf('day'), end];
};

const yuan = (value?: number) =>
  `¥${(value ?? 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

const percent = (value?: number) => `${(value ?? 0).toFixed(2)}%`;

const hasData = (rows?: unknown[]) => Boolean(rows && rows.length > 0);

const toNumber = (value: unknown) => {
  if (typeof value === 'number') return value;
  if (typeof value === 'string') return Number(value) || 0;
  return 0;
};

const yuanTooltip = (value: unknown) => yuan(toNumber(value));

const moneyAwareTooltip = (
  value: unknown,
  name: unknown,
): [ReactNode, string] => {
  const label = String(name ?? '');
  const shouldFormatAsMoney =
    label.includes('营收') || label.includes('金额') || label.includes('收入');
  return shouldFormatAsMoney
    ? [yuanTooltip(value), label]
    : [
        `${toNumber(value).toLocaleString('zh-CN')}${
          label.includes('小时')
            ? '小时'
            : label.includes('用户')
            ? '人'
            : label.includes('出杯')
            ? '杯'
            : label.includes('订单') || label.includes('开通')
            ? '单'
            : ''
        }`,
        label,
      ];
};

const Dashboard = () => {
  const [preset, setPreset] = useState<RangePreset>('7d');
  const [range, setRange] = useState<[Dayjs, Dayjs]>(() => presetToRange('7d'));
  const [granularity, setGranularity] = useState<Granularity>('day');
  const [activeTab, setActiveTab] = useState<DashboardTabKey>('overview');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<DashboardData>({});

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: API.StatsOverviewParams = {
        StartDate: range[0].format('YYYY-MM-DD'),
        EndDate: range[1].format('YYYY-MM-DD'),
        Granularity: granularity,
      };
      const [
        opsRes,
        cateringRes,
        playRes,
        userRes,
        couponRes,
        referralRes,
        membershipRes,
        walletRes,
        pointRes,
        insightsRes,
      ] = await Promise.all([
        getOpsOverview(params),
        getCateringOverview(params),
        getPlayOverview(params),
        getUserOverview(params),
        getCouponOverview(params),
        getReferralOverview(params),
        getMembershipOverview(params),
        getWalletOverview(params),
        getPointOverview(params),
        getUserInsights({ ...params, Limit: 50 }),
      ]);

      const responses = [
        opsRes,
        cateringRes,
        playRes,
        userRes,
        couponRes,
        referralRes,
        membershipRes,
        walletRes,
        pointRes,
        insightsRes,
      ];
      const failed = responses.find((res) => res.Code !== 0 || !res.Data);
      if (failed) {
        message.error(failed.Message || failed.Msg || '加载统计数据失败');
        return;
      }
      setData({
        ops: opsRes.Data,
        catering: cateringRes.Data,
        play: playRes.Data,
        user: userRes.Data,
        coupon: couponRes.Data,
        referral: referralRes.Data,
        membership: membershipRes.Data,
        wallet: walletRes.Data,
        point: pointRes.Data,
        insights: insightsRes.Data,
      });
    } catch (error) {
      message.error('加载统计数据失败');
    } finally {
      setLoading(false);
    }
  }, [range, granularity]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handlePreset = (value: RangePreset) => {
    setPreset(value);
    if (value !== 'custom') {
      setRange(presetToRange(value));
    }
  };

  const opsSummary = data.ops?.Summary;
  const cateringSummary = data.catering?.Summary;
  const playSummary = data.play?.Summary;
  const couponSummary = data.coupon?.Summary;
  const referralSummary = data.referral?.Summary;
  const userSummary = data.user?.Summary;
  const membershipSummary = data.membership?.Summary;
  const walletSummary = data.wallet?.Summary;
  const pointSummary = data.point?.Summary;

  const opsTrendData = useMemo(() => data.ops?.Trend ?? [], [data.ops]);
  const cateringTrendData = useMemo(
    () => data.catering?.Trend ?? [],
    [data.catering],
  );
  const playTrendData = useMemo(() => data.play?.Trend ?? [], [data.play]);
  const rankingData = useMemo(
    () => [...(data.catering?.DishRanking ?? [])].reverse(),
    [data.catering],
  );
  const hourlyData = useMemo(
    () =>
      (data.catering?.Hourly ?? []).map((item) => ({
        ...item,
        HourLabel: `${item.Hour}:00`,
      })),
    [data.catering],
  );
  const categoryData = data.catering?.Category ?? [];
  const cateringPaymentData = data.catering?.Payment ?? [];
  const playPaymentData = data.play?.Payment ?? [];
  const playBillingData = data.play?.BillingMode ?? [];
  const couponPromotions = data.coupon?.Promotions ?? [];
  const referralTrend = data.referral?.Trend ?? [];
  const referralShares = data.referral?.ShareRanking ?? [];
  const sourceStores = data.user?.SourceStore ?? [];
  const membershipTrend = data.membership?.Trend ?? [];
  const membershipSources = data.membership?.SourceDistribution ?? [];
  const walletTrend = data.wallet?.Trend ?? [];
  const walletTiers = data.wallet?.TierDistribution ?? [];
  const pointTrend = data.point?.Trend ?? [];
  const pointRanking = data.point?.RedeemRanking ?? [];
  const insightItems = data.insights?.Items ?? [];

  const renderChartCard = (
    title: string,
    hasData: boolean,
    chart: ReactNode,
    extra?: ReactNode,
  ) => (
    <Card title={title} extra={extra} bodyStyle={{ height: 320 }}>
      {hasData ? (
        <InteractiveChart
          chart={chart as ReactElement}
          initialSelection={title === '经营趋势' ? 'Revenue' : 'all'}
        />
      ) : (
        <div
          style={{
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Empty description="暂无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        </div>
      )}
    </Card>
  );

  const renderMetric = (
    title: string,
    value?: number,
    options?: {
      prefix?: string;
      suffix?: string;
      precision?: number;
      color?: string;
    },
  ) => (
    <Col xs={12} sm={12} md={6} xl={4}>
      <Card>
        <Statistic
          title={title}
          value={value === null || value === undefined ? '—' : value}
          precision={options?.precision}
          prefix={options?.prefix}
          suffix={options?.suffix}
          valueStyle={options?.color ? { color: options.color } : undefined}
        />
      </Card>
    </Col>
  );

  const couponColumns = [
    {
      title: '活动',
      dataIndex: 'ActivityName',
      render: (_: string, record: API.CouponOverview['Promotions'][number]) => (
        <Space direction="vertical" size={0}>
          <Space>
            <Text strong>{record.ActivityName}</Text>
            {record.IsReferralCoupon && <Tag color="blue">老带新/新人券</Tag>}
          </Space>
          <Text type="secondary">{record.Title || record.CouponTypeText}</Text>
        </Space>
      ),
    },
    { title: '领取', dataIndex: 'ReceivedCount', width: 90 },
    { title: '核销', dataIndex: 'UsedCount', width: 90 },
    {
      title: '核销率',
      dataIndex: 'UseRate',
      width: 100,
      render: (value: number) => percent(value),
    },
    { title: '带动订单', dataIndex: 'OrderCount', width: 100 },
    {
      title: '带动金额',
      dataIndex: 'Revenue',
      width: 120,
      render: (value: number) =>
        value === null || value === undefined ? '—' : yuan(value),
    },
    {
      title: '优惠金额',
      dataIndex: 'DiscountAmount',
      width: 120,
      render: (value: number) =>
        value === null || value === undefined ? '—' : yuan(value),
    },
  ];

  const insightColumns = [
    {
      title: '用户',
      dataIndex: 'NickName',
      width: 220,
      render: (_: string, record: API.UserInsightItem) => (
        <Space direction="vertical" size={0}>
          <Text strong>{record.NickName || '未命名用户'}</Text>
          <Text type="secondary">{record.OpenId}</Text>
        </Space>
      ),
    },
    {
      title: '标签',
      dataIndex: 'Tags',
      width: 220,
      render: (tags: string[]) => (
        <Space wrap size={[0, 4]}>
          {(tags || []).map((tag) => (
            <Tag key={tag} color={tag === '月卡用户' ? 'blue' : undefined}>
              {tag}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '总订单',
      dataIndex: 'TotalOrderCount',
      sorter: (a: API.UserInsightItem, b: API.UserInsightItem) =>
        a.TotalOrderCount - b.TotalOrderCount,
    },
    { title: '游玩单', dataIndex: 'PlayOrderCount' },
    { title: '饮品单', dataIndex: 'CateringOrderCount' },
    {
      title: '消费金额',
      dataIndex: 'TotalRevenue',
      render: (value: number) =>
        value === null || value === undefined ? '—' : yuan(value),
      sorter: (a: API.UserInsightItem, b: API.UserInsightItem) =>
        a.TotalRevenue - b.TotalRevenue,
    },
    { title: '游玩小时', dataIndex: 'TotalPlayHours' },
    { title: '用券数', dataIndex: 'CouponUsedCount' },
    {
      title: '储值充值',
      dataIndex: 'WalletRechargeAmount',
      render: (value: number) =>
        value === null || value === undefined ? '—' : yuan(value),
    },
    { title: '积分余额', dataIndex: 'PointBalance' },
    { title: '最近消费', dataIndex: 'LastOrderAt', width: 170 },
  ];

  const overviewTab = (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Row gutter={[16, 16]}>
        {renderMetric('总营收（桌游+饮品）', opsSummary?.TotalRevenue, {
          prefix: '¥',
          precision: 2,
          color: BRAND_BLUE,
        })}
        {renderMetric('桌游营收', opsSummary?.PlayRevenue, {
          prefix: '¥',
          precision: 2,
        })}
        {renderMetric('饮品营收', opsSummary?.CateringRevenue, {
          prefix: '¥',
          precision: 2,
        })}
        {renderMetric('订单数', opsSummary?.OrderCount, { suffix: '单' })}
        {renderMetric('新增用户', opsSummary?.NewUsers, { suffix: '人' })}
        {renderMetric('活跃用户', opsSummary?.ActiveUsers, { suffix: '人' })}
        {renderMetric('储值充值', opsSummary?.WalletRechargeAmount, {
          prefix: '¥',
          precision: 2,
        })}
        {renderMetric('积分消耗', opsSummary?.PointConsumed, { suffix: '分' })}
      </Row>

      {renderChartCard(
        '经营趋势',
        hasData(opsTrendData),
        <LineChart
          data={opsTrendData}
          margin={{ top: 8, right: 24, left: 0, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="Date" />
          <YAxis yAxisId="left" unit="元" />
          <YAxis yAxisId="right" orientation="right" allowDecimals={false} />
          <Tooltip formatter={moneyAwareTooltip} />
          <Legend />
          {OPS_SERIES.map((series) => (
            <Line
              key={series.key}
              yAxisId={series.axis}
              type="monotone"
              dataKey={series.key}
              name={series.name}
              stroke={series.color}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </LineChart>,
      )}
    </Space>
  );

  const promotionTab = (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message="当前促销分析基于领取、核销、支付订单等交易结果口径；曝光、点击、支付放弃等漏斗数据需要后续小程序埋点补齐。"
      />
      <Row gutter={[16, 16]}>
        {renderMetric('领券数', couponSummary?.ReceivedCount, { suffix: '张' })}
        {renderMetric('核销数', couponSummary?.UsedCount, { suffix: '张' })}
        {renderMetric('核销率', couponSummary?.UseRate, { suffix: '%' })}
        {renderMetric('带动订单', couponSummary?.OrderCount, { suffix: '单' })}
        {renderMetric('带动金额', couponSummary?.Revenue, {
          prefix: '¥',
          precision: 2,
        })}
        {renderMetric('优惠金额', couponSummary?.DiscountAmount, {
          prefix: '¥',
          precision: 2,
        })}
        {renderMetric('邀请绑定', referralSummary?.BoundCount, {
          suffix: '人',
        })}
        {renderMetric('邀请首单率', referralSummary?.FirstOrderRate, {
          suffix: '%',
        })}
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <Card title="券活动效果">
            <Table
              rowKey="PromotionId"
              columns={couponColumns}
              dataSource={couponPromotions}
              pagination={{ pageSize: 8 }}
              size="small"
            />
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          {renderChartCard(
            '老带新漏斗趋势',
            hasData(referralTrend),
            <LineChart
              data={referralTrend}
              margin={{ top: 8, right: 24, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="Date" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="BoundCount"
                name="绑定"
                stroke={BRAND_BLUE}
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="FirstOrderCount"
                name="首单完成"
                stroke="#11132B"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="InviterRewardedCount"
                name="奖励发放"
                stroke="#FA8C16"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>,
          )}
        </Col>
      </Row>
      <Card title="老带新分享渠道 TOP10">
        <Table
          rowKey="ShareId"
          columns={[
            { title: 'ShareId', dataIndex: 'ShareId' },
            { title: '绑定数', dataIndex: 'BoundCount' },
            { title: '首单数', dataIndex: 'FirstOrderCount' },
            {
              title: '首单率',
              dataIndex: 'FirstOrderRate',
              render: (value: number) => percent(value),
            },
          ]}
          dataSource={referralShares}
          pagination={false}
          size="small"
        />
      </Card>
    </Space>
  );

  const userTab = (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Row gutter={[16, 16]}>
        {renderMetric('新增用户', userSummary?.NewUsers, { suffix: '人' })}
        {renderMetric('付费用户', userSummary?.PaidUsers, { suffix: '人' })}
        {renderMetric('新付费用户', userSummary?.NewPaidUsers, {
          suffix: '人',
        })}
        {renderMetric('复购/老客', userSummary?.ReturningPaidUsers, {
          suffix: '人',
        })}
        {renderMetric('新客付费率', userSummary?.NewUserPayRate, {
          suffix: '%',
        })}
        {renderMetric('有效月卡用户', membershipSummary?.ActiveMonthCardUsers, {
          suffix: '人',
        })}
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          {renderChartCard(
            '新增用户趋势',
            hasData(data.user?.Trend),
            <BarChart
              data={data.user?.Trend ?? []}
              margin={{ top: 8, right: 24, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="Date" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar
                dataKey="NewUsers"
                name="新增用户"
                fill={BRAND_BLUE}
                radius={[4, 4, 0, 0]}
              />
            </BarChart>,
          )}
        </Col>
        <Col xs={24} xl={10}>
          {renderChartCard(
            '注册来源门店',
            hasData(sourceStores),
            <PieChart>
              <Tooltip />
              <Legend />
              <Pie
                data={sourceStores}
                dataKey="UserCount"
                nameKey="StoreName"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label
              >
                {sourceStores.map((entry, index) => (
                  <Cell
                    key={entry.StoreName}
                    fill={PIE_COLORS[index % PIE_COLORS.length]}
                  />
                ))}
              </Pie>
            </PieChart>,
          )}
        </Col>
      </Row>
      <Card title="用户洞察">
        <Table
          rowKey="OpenId"
          columns={insightColumns}
          dataSource={insightItems}
          pagination={{ pageSize: 10 }}
          scroll={{ x: 1300 }}
          size="small"
        />
      </Card>
    </Space>
  );

  const cateringTab = (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Row gutter={[16, 16]}>
        {renderMetric('饮品营收', cateringSummary?.Revenue, {
          prefix: '¥',
          precision: 2,
          color: BRAND_BLUE,
        })}
        {renderMetric('饮品订单', cateringSummary?.OrderCount, {
          suffix: '单',
        })}
        {renderMetric('饮品客单价', cateringSummary?.AvgOrderValue, {
          prefix: '¥',
          precision: 2,
        })}
        {renderMetric('出杯数', cateringSummary?.CupCount, { suffix: '杯' })}
      </Row>
      {renderChartCard(
        '饮品营收 / 订单趋势',
        hasData(cateringTrendData),
        <LineChart
          data={cateringTrendData}
          margin={{ top: 8, right: 24, left: 0, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="Date" />
          <YAxis yAxisId="left" unit="元" />
          <YAxis yAxisId="right" orientation="right" allowDecimals={false} />
          <Tooltip formatter={moneyAwareTooltip} />
          <Legend />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="Revenue"
            name="营收"
            stroke={BRAND_BLUE}
            strokeWidth={2}
            dot={false}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="OrderCount"
            name="订单数"
            stroke="#11132B"
            strokeWidth={2}
            dot={false}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="CupCount"
            name="出杯数"
            stroke="#FA8C16"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>,
      )}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          {renderChartCard(
            '热销餐品 TOP10',
            hasData(rankingData),
            <BarChart
              data={rankingData}
              layout="vertical"
              margin={{ top: 8, right: 24, left: 16, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" allowDecimals={false} />
              <YAxis type="category" dataKey="DishName" width={90} />
              <Tooltip />
              <Bar
                dataKey="Count"
                name="销量"
                fill={BRAND_BLUE}
                radius={[0, 4, 4, 0]}
              />
            </BarChart>,
          )}
        </Col>
        <Col xs={24} lg={12}>
          {renderChartCard(
            '时段分布',
            hourlyData.some((h) => h.OrderCount > 0 || h.CupCount > 0),
            <BarChart
              data={hourlyData}
              margin={{ top: 8, right: 24, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="HourLabel" interval={1} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Legend />
              <Bar
                dataKey="OrderCount"
                name="订单数"
                fill={BRAND_BLUE}
                radius={[4, 4, 0, 0]}
              />
              <Bar
                dataKey="CupCount"
                name="出杯数"
                fill="#7FA0FF"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>,
          )}
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          {renderChartCard(
            '品类占比（按营收）',
            hasData(categoryData),
            <PieChart>
              <Tooltip formatter={yuanTooltip} />
              <Legend />
              <Pie
                data={categoryData}
                dataKey="Revenue"
                nameKey="CategoryName"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label
              >
                {categoryData.map((entry, index) => (
                  <Cell
                    key={entry.CategoryName}
                    fill={PIE_COLORS[index % PIE_COLORS.length]}
                  />
                ))}
              </Pie>
            </PieChart>,
          )}
        </Col>
        <Col xs={24} lg={12}>
          {renderChartCard(
            '饮品支付方式',
            hasData(cateringPaymentData),
            <PieChart>
              <Tooltip formatter={yuanTooltip} />
              <Legend />
              <Pie
                data={cateringPaymentData}
                dataKey="Revenue"
                nameKey="PayTypeText"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label
              >
                {cateringPaymentData.map((entry, index) => (
                  <Cell
                    key={entry.PayTypeText}
                    fill={PIE_COLORS[index % PIE_COLORS.length]}
                  />
                ))}
              </Pie>
            </PieChart>,
          )}
        </Col>
      </Row>
    </Space>
  );

  const playTab = (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Row gutter={[16, 16]}>
        {renderMetric('桌游营收', playSummary?.Revenue, {
          prefix: '¥',
          precision: 2,
          color: BRAND_BLUE,
        })}
        {renderMetric('游玩订单', playSummary?.OrderCount, { suffix: '单' })}
        {renderMetric('游玩用户', playSummary?.UniqueUsers, { suffix: '人' })}
        {renderMetric('总游玩时长', playSummary?.TotalPlayHours, {
          suffix: '小时',
        })}
        {renderMetric('平均游玩时长', playSummary?.AvgPlayHours, {
          suffix: '小时',
        })}
        {renderMetric('桌游客单价', playSummary?.AvgOrderValue, {
          prefix: '¥',
          precision: 2,
        })}
      </Row>
      {renderChartCard(
        '桌游营收 / 时长趋势',
        hasData(playTrendData),
        <LineChart
          data={playTrendData}
          margin={{ top: 8, right: 24, left: 0, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="Date" />
          <YAxis yAxisId="left" unit="元" />
          <YAxis
            yAxisId="right"
            orientation="right"
            allowDecimals={false}
            unit="单"
          />
          <YAxis yAxisId="hours" orientation="right" unit="小时" />
          <Tooltip formatter={moneyAwareTooltip} />
          <Legend />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="Revenue"
            name="营收"
            stroke={BRAND_BLUE}
            strokeWidth={2}
            dot={false}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="OrderCount"
            name="订单数"
            stroke="#11132B"
            strokeWidth={2}
            dot={false}
          />
          <Line
            yAxisId="hours"
            type="monotone"
            dataKey="TotalPlayHours"
            name="游玩小时"
            stroke="#FA8C16"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>,
      )}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          {renderChartCard(
            '计费模式分布',
            hasData(playBillingData),
            <PieChart>
              <Tooltip formatter={yuanTooltip} />
              <Legend />
              <Pie
                data={playBillingData}
                dataKey="Revenue"
                nameKey="BillingModeText"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label
              >
                {playBillingData.map((entry, index) => (
                  <Cell
                    key={entry.BillingModeText}
                    fill={PIE_COLORS[index % PIE_COLORS.length]}
                  />
                ))}
              </Pie>
            </PieChart>,
          )}
        </Col>
        <Col xs={24} lg={12}>
          {renderChartCard(
            '桌游支付方式',
            hasData(playPaymentData),
            <PieChart>
              <Tooltip formatter={yuanTooltip} />
              <Legend />
              <Pie
                data={playPaymentData}
                dataKey="Revenue"
                nameKey="PayTypeText"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label
              >
                {playPaymentData.map((entry, index) => (
                  <Cell
                    key={entry.PayTypeText}
                    fill={PIE_COLORS[index % PIE_COLORS.length]}
                  />
                ))}
              </Pie>
            </PieChart>,
          )}
        </Col>
      </Row>
    </Space>
  );

  const assetTab = (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Row gutter={[16, 16]}>
        {renderMetric('月卡销售额（不含赠卡）', membershipSummary?.Revenue, {
          prefix: '¥',
          precision: 2,
        })}
        {renderMetric('总部赠卡补贴', membershipSummary?.SubsidyAmount, {
          prefix: '¥',
          precision: 2,
        })}
        {renderMetric('月卡开通', membershipSummary?.OpenCount, {
          suffix: '单',
        })}
        {renderMetric('月卡游玩单', membershipSummary?.PlayOrderCount, {
          suffix: '单',
        })}
        {renderMetric('储值充值', walletSummary?.RechargeAmount, {
          prefix: '¥',
          precision: 2,
        })}
        {renderMetric('储值消费', walletSummary?.ConsumeAmount, {
          prefix: '¥',
          precision: 2,
        })}
        {renderMetric('钱包余额沉淀', walletSummary?.BalanceTotal, {
          prefix: '¥',
          precision: 2,
        })}
        {renderMetric('积分发放', pointSummary?.EarnedPoints, { suffix: '分' })}
        {renderMetric('积分消耗', pointSummary?.ConsumedPoints, {
          suffix: '分',
        })}
        {renderMetric('积分余额沉淀', pointSummary?.BalanceTotal, {
          suffix: '分',
        })}
        {renderMetric('兑换订单', pointSummary?.RedeemOrderCount, {
          suffix: '单',
        })}
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          {renderChartCard(
            '月卡开通趋势',
            hasData(membershipTrend),
            <BarChart
              data={membershipTrend}
              margin={{ top: 8, right: 24, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="Date" />
              <YAxis yAxisId="money" unit="元" />
              <YAxis
                yAxisId="count"
                orientation="right"
                allowDecimals={false}
                unit="单"
              />
              <Tooltip formatter={moneyAwareTooltip} />
              <Legend />
              <Bar
                yAxisId="money"
                dataKey="Revenue"
                name="月卡收入"
                fill={BRAND_BLUE}
                radius={[4, 4, 0, 0]}
              />
              <Bar
                yAxisId="count"
                dataKey="OpenCount"
                name="开通数"
                fill="#7FA0FF"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>,
          )}
        </Col>
        <Col xs={24} xl={8}>
          {renderChartCard(
            '储值充值趋势',
            hasData(walletTrend),
            <BarChart
              data={walletTrend}
              margin={{ top: 8, right: 24, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="Date" />
              <YAxis unit="元" />
              <Tooltip formatter={moneyAwareTooltip} />
              <Legend />
              <Bar
                dataKey="RechargeAmount"
                name="充值金额"
                fill={BRAND_BLUE}
                radius={[4, 4, 0, 0]}
              />
              <Bar
                dataKey="BonusAmount"
                name="赠送金额"
                fill="#7FA0FF"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>,
          )}
        </Col>
        <Col xs={24} xl={8}>
          {renderChartCard(
            '积分流动趋势',
            hasData(pointTrend),
            <LineChart
              data={pointTrend}
              margin={{ top: 8, right: 24, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="Date" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="EarnedPoints"
                name="发放积分"
                stroke={BRAND_BLUE}
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="ConsumedPoints"
                name="消耗积分"
                stroke="#11132B"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>,
          )}
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card title="月卡来源分布">
            <Table
              rowKey="Source"
              columns={[
                { title: '来源', dataIndex: 'SourceText' },
                {
                  title: '收入',
                  dataIndex: 'Revenue',
                  render: (value: number) =>
                    value === null || value === undefined ? '—' : yuan(value),
                },
                { title: '开通数', dataIndex: 'OpenCount' },
                { title: '赠送数', dataIndex: 'GiftedCount' },
              ]}
              dataSource={membershipSources}
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card title="储值档位分布">
            <Table
              rowKey={(record) => `${record.Amount}-${record.BonusAmount}`}
              columns={[
                { title: '档位', dataIndex: 'Label' },
                {
                  title: '充值金额',
                  dataIndex: 'Amount',
                  render: (value: number) =>
                    value === null || value === undefined ? '—' : yuan(value),
                },
                {
                  title: '赠送金额',
                  dataIndex: 'BonusAmount',
                  render: (value: number) =>
                    value === null || value === undefined ? '—' : yuan(value),
                },
                { title: '充值次数', dataIndex: 'RechargeCount' },
              ]}
              dataSource={walletTiers}
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card title="热门积分兑换">
            <Table
              rowKey="ProductName"
              columns={[
                { title: '商品', dataIndex: 'ProductName' },
                { title: '兑换数量', dataIndex: 'Quantity' },
                { title: '消耗积分', dataIndex: 'TotalPoints' },
              ]}
              dataSource={pointRanking}
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
      </Row>
    </Space>
  );

  return (
    <PageContainer
      header={{
        title: '运营分析大盘',
        subTitle: data.ops
          ? `${data.ops.StartDate} 至 ${data.ops.EndDate}`
          : undefined,
      }}
      extra={[
        ...(storeScopedDashboardTabs.has(activeTab)
          ? [
              <StoreSwitcher
                key="store"
                label="统计门店"
                selectStyle={{ width: 132 }}
                onChange={fetchData}
              />,
            ]
          : []),
        <Radio.Group
          key="preset"
          value={preset}
          onChange={(e) => handlePreset(e.target.value)}
          optionType="button"
          buttonStyle="solid"
        >
          <Radio.Button value="today">今日</Radio.Button>
          <Radio.Button value="yesterday">昨日</Radio.Button>
          <Radio.Button value="7d">近7天</Radio.Button>
          <Radio.Button value="30d">近30天</Radio.Button>
          <Radio.Button value="custom">自定义</Radio.Button>
        </Radio.Group>,
        <RangePicker
          key="range"
          value={range}
          allowClear={false}
          onChange={(values) => {
            if (values && values[0] && values[1]) {
              setPreset('custom');
              setRange([values[0], values[1]]);
            }
          }}
        />,
        <Radio.Group
          key="granularity"
          value={granularity}
          onChange={(e) => setGranularity(e.target.value)}
          optionType="button"
        >
          <Radio.Button value="day">日</Radio.Button>
          <Radio.Button value="week">周</Radio.Button>
          <Radio.Button value="month">月</Radio.Button>
        </Radio.Group>,
        <ReloadOutlined
          key="reload"
          onClick={fetchData}
          style={{ cursor: 'pointer', fontSize: 16 }}
        />,
      ]}
    >
      <Spin spinning={loading}>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <ScopeAlert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message="当前门店统计；— 表示该指标暂无可展示数据。全品牌储值余额、拉新与领券指标仅总部可见，不能作为本店收入。"
          />
          <Tabs
            activeKey={activeTab}
            onChange={(key) => setActiveTab(key as DashboardTabKey)}
            items={[
              { key: 'overview', label: '经营总览', children: overviewTab },
              {
                key: 'promotion',
                label: '促销与老带新',
                children: promotionTab,
              },
              { key: 'user', label: '用户洞察', children: userTab },
              { key: 'catering', label: '饮品分析', children: cateringTab },
              { key: 'play', label: '桌游分析', children: playTab },
              { key: 'asset', label: '月卡/储值/积分', children: assetTab },
            ]}
          />
        </Space>
      </Spin>
    </PageContainer>
  );
};

export default Dashboard;
