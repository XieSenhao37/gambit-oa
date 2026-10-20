import {
  getPricing,
  previewPricing,
  PricingData,
  savePricing,
} from '@/services/playPricing';
import {
  CalendarOutlined,
  ClockCircleOutlined,
  DeleteOutlined,
  InfoCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SaveOutlined,
} from '@ant-design/icons';
import { PageContainer } from '@ant-design/pro-components';
import {
  Alert,
  Button,
  Checkbox,
  DatePicker,
  Form,
  Input,
  InputNumber,
  message,
  Popconfirm,
  Radio,
  Select,
  Spin,
  Switch,
  Tabs,
  Tag,
  Tooltip,
} from 'antd';
import dayjs from 'dayjs';
import { useEffect, useRef, useState } from 'react';
import styles from './index.less';
import {
  emptyPrice,
  fromSchedule,
  regularDraft,
  toSchedule,
} from './pricingForm';

const kinds = [
  { value: 'common', label: '平日价' },
  { value: 'holiday', label: '周末／节假日价' },
];
const weekdays = [
  { label: '周一', value: 1 },
  { label: '周二', value: 2 },
  { label: '周三', value: 3 },
  { label: '周四', value: 4 },
  { label: '周五', value: 5 },
  { label: '周六', value: 6 },
  { label: '周日', value: 0 },
];
const required = [{ required: true, message: '请填写' }];
function weekLabel(days: number[]) {
  if (!days.length) return '';
  if (days.length === 7) return '周一至周日';
  if (days.length === 3 && [0, 5, 6].every((d) => days.includes(d)))
    return '周五至周日';
  if (days.length === 4 && [1, 2, 3, 4].every((d) => days.includes(d)))
    return '周一至周四';
  return weekdays
    .filter((d) => days.includes(d.value))
    .map((d) => d.label)
    .join('、');
}
function DateValue({
  value,
  onChange,
  id,
  placeholder = '选择日期',
}: {
  value?: string;
  id?: string;
  onChange?: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <DatePicker
      id={id}
      value={value && dayjs(value).isValid() ? dayjs(value) : null}
      onChange={(v) => onChange?.(v?.format('YYYY-MM-DD') ?? '')}
      format="YYYY-MM-DD"
      placeholder={placeholder}
      style={{ width: '100%' }}
    />
  );
}
function PriceFields({
  path,
  absolutePath = path,
}: {
  path: (string | number)[];
  absolutePath?: (string | number)[];
}) {
  return (
    <Form.Item noStyle shouldUpdate>
      {(form) => {
        const price = form.getFieldValue(absolutePath) ?? emptyPrice;
        const daily = price.Mode === 'daily_cap';
        return (
          <>
            <Form.Item
              name={[...path, 'Mode']}
              label="收费方式"
              rules={required}
            >
              <Radio.Group
                className={styles.modeSelector}
                optionType="button"
                buttonStyle="solid"
                options={[
                  { value: 'daily_cap', label: '全天封顶' },
                  { value: 'bundle', label: '优惠＋续时' },
                  ...(price.Mode === 'legacy'
                    ? [{ value: 'legacy', label: '历史配置' }]
                    : []),
                ]}
              />
            </Form.Item>
            {price.Mode === 'legacy' && (
              <Alert
                type="warning"
                showIcon
                className={styles.legacyNotice}
                message="已保留历史价格。切换收费方式将改变计价，请先试算。"
              />
            )}
            <div className={styles.priceInputs}>
              <Form.Item
                name={[...path, 'Price']}
                label="小时单价"
                rules={required}
              >
                <InputNumber
                  min={0}
                  max={100000}
                  precision={2}
                  addonAfter="元 / 小时"
                />
              </Form.Item>
              {!daily && (
                <Form.Item
                  name={[...path, 'MaxHour']}
                  label="优惠时长"
                  rules={required}
                >
                  <InputNumber
                    min={1}
                    max={24}
                    precision={0}
                    addonAfter="小时"
                  />
                </Form.Item>
              )}
              <Form.Item
                name={[...path, 'MaxTotal']}
                label={daily ? '全天封顶价' : '优惠价格'}
                tooltip={
                  daily ? undefined : '优惠时长内按小时计费，最多收取此金额'
                }
                rules={required}
              >
                <InputNumber
                  min={0}
                  max={100000}
                  precision={2}
                  addonAfter="元"
                />
              </Form.Item>
              {!daily && (
                <Form.Item
                  name={[...path, 'AdditionPrice']}
                  label="续时单价"
                  rules={required}
                >
                  <InputNumber
                    min={0}
                    max={100000}
                    precision={2}
                    addonAfter="元 / 小时"
                  />
                </Form.Item>
              )}
            </div>
          </>
        );
      }}
    </Form.Item>
  );
}
function EmptyRules({
  icon,
  title,
  text,
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
}) {
  return (
    <div className={styles.emptyRules}>
      <span className={styles.emptyIcon}>{icon}</span>
      <strong>{title}</strong>
      <span>{text}</span>
    </div>
  );
}

export default function PlayPricing() {
  const [form] = Form.useForm();
  const [data, setData] = useState<PricingData>();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [ready, setReady] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [activeTab, setActiveTab] = useState('times');
  const [previewAt, setPreviewAt] = useState(dayjs());
  const [hours, setHours] = useState(3);
  const [preview, setPreview] = useState<{
    amount: number;
    rule: string;
    hours: number;
  }>();
  const [previewing, setPreviewing] = useState(false);
  const previewVersion = useRef(0);
  const [range, setRange] = useState<any>(null);
  const [rangeKind, setRangeKind] = useState('holiday');
  const holidayDays = Form.useWatch('HolidayWeekdays', form) ?? [0, 5, 6];
  const commonDays = weekdays
    .map((d) => d.value)
    .filter((d) => !holidayDays.includes(d));
  const timeRules = Form.useWatch('TimeRules', form) ?? [];
  const dateOverrides = Form.useWatch('DateOverrides', form) ?? [];
  const specials = Form.useWatch('Specials', form) ?? [];
  const clearPreview = () => {
    previewVersion.current += 1;
    setPreview(undefined);
  };
  const changed = () => {
    setDirty(true);
    clearPreview();
  };
  const load = async () => {
    setLoading(true);
    setReady(false);
    clearPreview();
    try {
      const res = await getPricing();
      if (res.Code !== 0 || !res.Data) throw Error(res.Message || '读取失败');
      setData(res.Data);
      form.resetFields();
      form.setFieldsValue(fromSchedule(res.Data.Config));
      setDirty(false);
      setReady(true);
    } catch (e: any) {
      message.error(e.message || '读取失败');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);
  const config = async () => {
    try {
      await form.validateFields();
      return toSchedule(form.getFieldsValue(true));
    } catch (e: any) {
      const field = e.errorFields?.[0]?.name?.[0];
      if (field)
        setActiveTab(
          (
            {
              TimeRules: 'times',
              DateOverrides: 'dates',
              Specials: 'specials',
            } as Record<string, string>
          )[field] ?? activeTab,
        );
      throw e;
    }
  };
  const save = async () => {
    setSaving(true);
    try {
      const res = await savePricing(await config(), data!.Revision);
      if (res.Code !== 0 || !res.Data) throw Error(res.Message || '保存失败');
      setData(res.Data);
      form.setFieldsValue(fromSchedule(res.Data.Config));
      clearPreview();
      setDirty(false);
      message.success('计价策略已保存');
    } catch (e: any) {
      if (!e.errorFields) message.error(e.message || '保存失败，请重试');
    } finally {
      setSaving(false);
    }
  };
  const simulate = async () => {
    setPreviewing(true);
    setPreview(undefined);
    const version = ++previewVersion.current;
    const requestedHours = hours;
    try {
      const res = await previewPricing(
        await config(),
        previewAt.format('YYYY-MM-DD HH:mm'),
        requestedHours,
      );
      if (version !== previewVersion.current) return;
      if (res.Code !== 0 || !res.Data) throw Error(res.Message || '试算失败');
      setPreview({
        amount: res.Data.Amount,
        rule: res.Data.Rule,
        hours: requestedHours,
      });
    } catch (e: any) {
      if (version === previewVersion.current && !e.errorFields)
        message.error(e.message || '试算失败');
    } finally {
      setPreviewing(false);
    }
  };
  const addRange = () => {
    if (!range?.[0] || !range?.[1]) {
      message.info('请选择日期范围');
      return;
    }
    if (range[1].diff(range[0], 'day') > 365) {
      message.error('每次最多添加 366 天');
      return;
    }
    const map = Object.fromEntries(
      (form.getFieldValue('DateOverrides') ?? []).map((r: any) => [
        r.Date,
        r.DayType,
      ]),
    );
    for (let d = range[0]; !d.isAfter(range[1], 'day'); d = d.add(1, 'day'))
      map[d.format('YYYY-MM-DD')] = rangeKind;
    form.setFieldValue(
      'DateOverrides',
      Object.entries(map)
        .sort()
        .map(([Date, DayType]) => ({ Date, DayType })),
    );
    changed();
    setRange(null);
  };
  const tabLabel = (title: string, count: number) => (
    <span className={styles.tabLabel}>
      {title}
      {count > 0 && <span className={styles.count}>{count}</span>}
    </span>
  );
  return (
    <PageContainer
      title={false}
      pageHeaderRender={false}
      className={styles.container}
    >
      <div className={styles.page}>
        <header className={styles.header}>
          <h1>桌游计价管理</h1>
          <div className={styles.headerActions}>
            <Tag color={dirty ? 'gold' : undefined}>
              {dirty ? '有未保存的修改' : data?.Config ? '已保存' : '待配置'}
            </Tag>
            <Button
              icon={<ReloadOutlined />}
              disabled={!ready || saving}
              onClick={() => {
                form.setFieldsValue(regularDraft);
                changed();
                message.info(
                  '默认价格已恢复到草稿，保存后生效；时段和指定日期规则保留',
                );
              }}
            >
              恢复默认价格
            </Button>
          </div>
        </header>
        <Spin spinning={loading}>
          {!ready && !loading && (
            <Alert
              type="error"
              showIcon
              message="无法读取计价配置"
              action={
                <Button size="small" onClick={load}>
                  重新加载
                </Button>
              }
            />
          )}
          {!data?.Config && ready && (
            <Alert
              className={styles.loadNotice}
              type="warning"
              showIcon
              message="当前门店尚未配置价格，请填写并保存。"
            />
          )}
          <Form
            form={form}
            layout="vertical"
            onValuesChange={changed}
            disabled={!ready || saving}
            requiredMark={false}
          >
            <section className={styles.baseSection}>
              <div className={styles.sectionHeading}>
                <div>
                  <h2>基础价格</h2>
                  <span>按日期自动应用</span>
                </div>
                <Tooltip title="指定日期独立价格优先，其次为入场时段，最后为基础价格。跨时段沿用入场方案；计时按北京时间，至少 1 小时，满 30 分钟进到下一小时。">
                  <InfoCircleOutlined aria-label="查看计价规则" />
                </Tooltip>
              </div>
              <div className={styles.calendarSettings}>
                <Form.Item name="HolidayWeekdays" label="与节假日同价的星期">
                  <Checkbox.Group
                    className={styles.weekdays}
                    options={weekdays}
                  />
                </Form.Item>
                <div className={styles.adjustedWorkdays}>
                  <span>调休补班按平日价</span>
                  <Form.Item
                    name="UseAdjustedWorkdays"
                    valuePropName="checked"
                    noStyle
                  >
                    <Switch size="small" aria-label="调休补班按平日价" />
                  </Form.Item>
                </div>
              </div>
              <div className={styles.baseGrid}>
                <div className={styles.priceCard}>
                  <div className={styles.priceCardHeading}>
                    <span className={styles.priceIcon}>
                      <CalendarOutlined />
                    </span>
                    <div>
                      <h3>平日价格</h3>
                      <span>{weekLabel(commonDays) || '仅手动指定的平日'}</span>
                    </div>
                  </div>
                  <PriceFields path={['Common']} />
                </div>
                <div className={`${styles.priceCard} ${styles.holidayCard}`}>
                  <div className={styles.priceCardHeading}>
                    <span className={styles.priceIcon}>
                      <CalendarOutlined />
                    </span>
                    <div>
                      <h3>周末／节假日价格</h3>
                      <span>
                        {holidayDays.length
                          ? `${weekLabel(holidayDays)} · 节假日`
                          : '仅节假日'}
                      </span>
                    </div>
                  </div>
                  <PriceFields path={['Holiday']} />
                </div>
              </div>
            </section>
            <div className={styles.detailsGrid}>
              <section className={styles.ruleSection}>
                <div className={styles.sectionHeading}>
                  <div>
                    <h2>灵活定价</h2>
                    <span>时段优惠、活动与临时调整</span>
                  </div>
                </div>
                <Tabs
                  activeKey={activeTab}
                  onChange={setActiveTab}
                  className={styles.ruleTabs}
                  items={[
                    {
                      key: 'times',
                      label: tabLabel('入场时段', timeRules.length),
                      forceRender: true,
                      children: (
                        <Form.List name="TimeRules">
                          {(fields, { add, remove }) => (
                            <>
                              <div className={styles.tabIntro}>
                                <span>按入场时刻匹配，支持跨午夜。</span>
                                <Button
                                  size="small"
                                  icon={<PlusOutlined />}
                                  onClick={() => {
                                    add({
                                      Name: '',
                                      DayType: 'any',
                                      StartDate: '',
                                      EndDate: '',
                                      StartTime: '14:00',
                                      EndTime: '18:00',
                                      Price: { ...emptyPrice },
                                    });
                                    changed();
                                  }}
                                >
                                  添加时段
                                </Button>
                              </div>
                              {!fields.length && (
                                <EmptyRules
                                  icon={<ClockCircleOutlined />}
                                  title="暂无时段价格"
                                  text="如需下午场或晚间优惠，可添加专属时段。"
                                />
                              )}
                              {fields.map(({ key, name }, i) => (
                                <div key={key} className={styles.ruleCard}>
                                  <div className={styles.ruleCardHeading}>
                                    <strong>
                                      时段 {String(i + 1).padStart(2, '0')}
                                    </strong>
                                    <Button
                                      type="text"
                                      size="small"
                                      danger
                                      icon={<DeleteOutlined />}
                                      aria-label={`删除时段 ${i + 1}`}
                                      onClick={() => {
                                        remove(name);
                                        changed();
                                      }}
                                    >
                                      删除
                                    </Button>
                                  </div>
                                  <div className={styles.ruleInputs}>
                                    <Form.Item
                                      name={[name, 'Name']}
                                      label="时段名称"
                                      rules={required}
                                    >
                                      <Input
                                        placeholder="例如：下午场优惠"
                                        maxLength={60}
                                      />
                                    </Form.Item>
                                    <Form.Item
                                      name={[name, 'DayType']}
                                      label="适用日期"
                                      rules={required}
                                    >
                                      <Select
                                        options={[
                                          { value: 'any', label: '所有日期' },
                                          ...kinds,
                                        ]}
                                      />
                                    </Form.Item>
                                    <Form.Item
                                      name={[name, 'StartTime']}
                                      label="入场开始"
                                      rules={required}
                                    >
                                      <Input
                                        prefix={<ClockCircleOutlined />}
                                        placeholder="14:00"
                                        maxLength={5}
                                      />
                                    </Form.Item>
                                    <Form.Item
                                      name={[name, 'EndTime']}
                                      label="入场结束"
                                      tooltip="不含结束时刻；可填 24:00。跨午夜可设置如 22:00 至 02:00。"
                                      rules={required}
                                    >
                                      <Input
                                        prefix={<ClockCircleOutlined />}
                                        placeholder="18:00 / 24:00"
                                        maxLength={5}
                                      />
                                    </Form.Item>
                                    <Form.Item
                                      name={[name, 'StartDate']}
                                      label="生效开始"
                                      tooltip="起止日期都留空时长期生效"
                                    >
                                      <DateValue placeholder="不限日期" />
                                    </Form.Item>
                                    <Form.Item
                                      name={[name, 'EndDate']}
                                      label="生效结束"
                                    >
                                      <DateValue placeholder="不限日期" />
                                    </Form.Item>
                                  </div>
                                  <div className={styles.rulePrice}>
                                    <PriceFields
                                      path={[name, 'Price']}
                                      absolutePath={[
                                        'TimeRules',
                                        name,
                                        'Price',
                                      ]}
                                    />
                                  </div>
                                </div>
                              ))}
                            </>
                          )}
                        </Form.List>
                      ),
                    },
                    {
                      key: 'dates',
                      label: tabLabel('日期调整', dateOverrides.length),
                      forceRender: true,
                      children: (
                        <>
                          <div className={styles.tabIntro}>
                            <span>为选定日期切换平日或节假日价格。</span>
                          </div>
                          <div className={styles.rangeToolbar}>
                            <DatePicker.RangePicker
                              value={range}
                              onChange={setRange}
                            />
                            <Select
                              value={rangeKind}
                              onChange={setRangeKind}
                              options={kinds}
                            />
                            <Button icon={<PlusOutlined />} onClick={addRange}>
                              应用日期范围
                            </Button>
                          </div>
                          <Form.List name="DateOverrides">
                            {(fields, { remove }) => (
                              <>
                                {!fields.length && (
                                  <EmptyRules
                                    icon={<CalendarOutlined />}
                                    title="暂无手动调整"
                                    text="当前按星期与国家放假安排自动判断。"
                                  />
                                )}
                                {fields.map(({ key, name }) => (
                                  <div key={key} className={styles.dateRow}>
                                    <Form.Item
                                      name={[name, 'Date']}
                                      rules={required}
                                    >
                                      <DateValue />
                                    </Form.Item>
                                    <Form.Item
                                      name={[name, 'DayType']}
                                      rules={required}
                                    >
                                      <Select options={kinds} />
                                    </Form.Item>
                                    <Button
                                      type="text"
                                      onClick={() => {
                                        remove(name);
                                        changed();
                                      }}
                                    >
                                      恢复自动
                                    </Button>
                                  </div>
                                ))}
                              </>
                            )}
                          </Form.List>
                        </>
                      ),
                    },
                    {
                      key: 'specials',
                      label: tabLabel('指定日期价格', specials.length),
                      forceRender: true,
                      children: (
                        <Form.List name="Specials">
                          {(fields, { add, remove }) => (
                            <>
                              <div className={styles.tabIntro}>
                                <span>
                                  指定日期全日使用独立价格，优先于时段规则。
                                </span>
                                <Button
                                  size="small"
                                  icon={<PlusOutlined />}
                                  onClick={() => {
                                    add({ Date: '', Price: { ...emptyPrice } });
                                    changed();
                                  }}
                                >
                                  添加日期
                                </Button>
                              </div>
                              {!fields.length && (
                                <EmptyRules
                                  icon={<CalendarOutlined />}
                                  title="暂无独立日期价格"
                                  text="适用于活动、包场或单日促销。"
                                />
                              )}
                              {fields.map(({ key, name }, i) => (
                                <div key={key} className={styles.ruleCard}>
                                  <div className={styles.ruleCardHeading}>
                                    <strong>
                                      日期价格 {String(i + 1).padStart(2, '0')}
                                    </strong>
                                    <Button
                                      type="text"
                                      size="small"
                                      danger
                                      icon={<DeleteOutlined />}
                                      aria-label={`删除日期价格 ${i + 1}`}
                                      onClick={() => {
                                        remove(name);
                                        changed();
                                      }}
                                    >
                                      删除
                                    </Button>
                                  </div>
                                  <Form.Item
                                    name={[name, 'Date']}
                                    label="适用日期"
                                    rules={required}
                                  >
                                    <DateValue />
                                  </Form.Item>
                                  <PriceFields
                                    path={[name, 'Price']}
                                    absolutePath={['Specials', name, 'Price']}
                                  />
                                </div>
                              ))}
                            </>
                          )}
                        </Form.List>
                      ),
                    },
                    {
                      key: 'calendar',
                      label: '节假日历',
                      children: data ? (
                        <>
                          <div className={styles.tabIntro}>
                            <span>{data.Calendar.Year} 年国家放假安排</span>
                            <a
                              href={data.Calendar.Source}
                              target="_blank"
                              rel="noreferrer"
                            >
                              官方来源 ↗
                            </a>
                          </div>
                          <div className={styles.holidayList}>
                            {data.Calendar.Holidays.map((h) => (
                              <div key={h.Name} className={styles.holidayRow}>
                                <strong>{h.Name}</strong>
                                <span>
                                  {dayjs(h.Start).format('MM月DD日')} —{' '}
                                  {dayjs(h.End).format('MM月DD日')}
                                </span>
                                <Tag>
                                  {dayjs(h.End).diff(dayjs(h.Start), 'day') + 1}{' '}
                                  天
                                </Tag>
                              </div>
                            ))}
                          </div>
                          <div className={styles.calendarNote}>
                            <strong>调休补班日</strong>
                            <div className={styles.workdayTags}>
                              {data.Calendar.Workdays.map((d) => (
                                <Tag key={d}>{dayjs(d).format('MM月DD日')}</Tag>
                              ))}
                            </div>
                            <p>
                              全国放假范围使用节假日价。新年份的农历假期与调休安排需维护，也可在“日期调整”中手动设置。
                            </p>
                          </div>
                        </>
                      ) : null,
                    },
                  ]}
                />
              </section>
              <aside className={styles.previewSection}>
                <div className={styles.sectionHeading}>
                  <div>
                    <h2>价格试算</h2>
                    <span>检查当前草稿的收费结果</span>
                  </div>
                  <ClockCircleOutlined />
                </div>
                <Form.Item label="入场时间" htmlFor="pricing-preview-at">
                  <DatePicker
                    id="pricing-preview-at"
                    showTime={{ format: 'HH:mm' }}
                    format="YYYY-MM-DD HH:mm"
                    value={previewAt}
                    onChange={(v) => {
                      if (v) setPreviewAt(v);
                      clearPreview();
                    }}
                    allowClear={false}
                  />
                </Form.Item>
                <Form.Item label="游玩时长" htmlFor="pricing-preview-hours">
                  <InputNumber
                    id="pricing-preview-hours"
                    min={1}
                    max={720}
                    precision={0}
                    value={hours}
                    onChange={(v) => {
                      setHours(v || 1);
                      clearPreview();
                    }}
                    addonAfter="小时"
                  />
                </Form.Item>
                <Button
                  block
                  type="primary"
                  ghost
                  disabled={!ready || saving}
                  loading={previewing}
                  onClick={simulate}
                >
                  试算当前草稿
                </Button>
                <div
                  className={`${styles.previewResult} ${
                    preview ? styles.previewReady : ''
                  }`}
                  aria-live="polite"
                >
                  <span>预计应收</span>
                  <div>
                    <small>¥</small>
                    {preview ? (preview.amount / 100).toFixed(2) : '—'}
                  </div>
                  <p>
                    {preview
                      ? `${preview.rule} · ${preview.hours} 小时`
                      : '选择入场时间与时长后试算'}
                  </p>
                </div>
              </aside>
            </div>
          </Form>
          <footer className={styles.saveBar}>
            <div>
              <span
                className={`${styles.statusDot} ${
                  dirty ? styles.dirtyDot : ''
                }`}
              />
              <span>
                {dirty
                  ? '修改尚未保存'
                  : data?.Config
                  ? '当前价格已保存'
                  : '填写后保存生效'}
              </span>
              <Tooltip title="保存会影响未结算订单的下次计价，已结算订单金额保持不变。">
                <span className={styles.saveHint}>
                  保存后用于未结算订单 <InfoCircleOutlined />
                </span>
              </Tooltip>
            </div>
            <div className={styles.saveActions}>
              <Popconfirm
                title="放弃草稿并重新加载已保存价格？"
                disabled={!dirty}
                onConfirm={load}
              >
                <Button
                  disabled={saving || loading}
                  onClick={() => {
                    if (!dirty) load();
                  }}
                >
                  重新加载
                </Button>
              </Popconfirm>
              <Popconfirm
                title="保存当前门店的计价策略？"
                description="将用于入场及未结算订单的计价。"
                onConfirm={save}
                disabled={!ready || saving}
              >
                <Button
                  type="primary"
                  icon={<SaveOutlined />}
                  disabled={!ready || (!dirty && !!data?.Config)}
                  loading={saving}
                >
                  保存修改
                </Button>
              </Popconfirm>
            </div>
          </footer>
        </Spin>
      </div>
    </PageContainer>
  );
}
