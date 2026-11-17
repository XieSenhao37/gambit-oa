import { Table } from '@/components/AdaptiveTable';
import type {
  ActivityStatus,
  CouponActivity,
  CouponFilters,
  CouponRecord,
} from '@/services/coupons';
import {
  listCouponActivities,
  listCouponRecords,
  saveCouponActivity,
} from '@/services/coupons';
import { PageContainer } from '@ant-design/pro-components';
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
  Row,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs, { Dayjs } from 'dayjs';
import { useEffect, useRef, useState } from 'react';

const { Text } = Typography;
const PAGE_SIZE = 20;
const roles: Record<number, string> = {
  1: '全职',
  2: '兼职',
  125: '店长',
  126: '管理员',
  127: '老板',
};
const types: Record<number, string> = {
  0: '时长券',
  1: '金额券',
  2: '折扣券',
  3: '免单券',
};
const scenes: Record<number, string> = { 0: '桌游', 1: '饮品' };
const statuses: Record<ActivityStatus, string> = {
  scheduled: '未开始',
  active: '发放中',
  ended: '已结束',
};
const DAY = 86400;

interface ActivityValues {
  ActivityName: string;
  Title: string;
  CouponType: number;
  DisplayAmount: number;
  DisplayMinimum: number;
  ExpireDays: number;
  Window: [Dayjs, Dayjs];
  ApplicableScenes: number[];
  CanReReceive: boolean;
  Description: string;
  Count: number;
  ControlRoles: number[];
}

const numericOptions = (items: Record<number, string>) =>
  Object.entries(items).map(([value, label]) => ({
    label,
    value: Number(value),
  }));

const currency = (cents: number) =>
  `¥${(cents / 100).toFixed(2).replace(/\.?0+$/, '')}`;

function couponBenefit(coupon: CouponActivity) {
  const { CouponType: type, Amount: amount } = coupon;
  if (type === 0) return `减 ${amount} 小时`;
  if (type === 1) return `减 ${currency(amount)}`;
  if (type === 2) return `${amount / 10} 折`;
  return types[type] || '优惠券';
}

function errorMessage(error: any, fallback: string) {
  return (
    error?.response?.data?.Message ||
    error?.data?.Message ||
    error?.message ||
    fallback
  );
}

export default function Coupons() {
  const [form] = Form.useForm<ActivityValues>();
  const type = Form.useWatch('CouponType', form);
  const [query, setQuery] = useState<CouponFilters>({ Page: 1 });
  const [reload, setReload] = useState(0);
  const [items, setItems] = useState<CouponActivity[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [editor, setEditor] = useState<CouponActivity | 'new'>();
  const editing = editor === 'new' ? undefined : editor;
  const locked = !!editing?.TermsLocked;
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const edited = useRef(false);
  const [saveError, setSaveError] = useState('');
  const [recordActivity, setRecordActivity] = useState<CouponActivity>();
  const [recordPage, setRecordPage] = useState(1);
  const [recordItems, setRecordItems] = useState<CouponRecord[]>([]);
  const [recordTotal, setRecordTotal] = useState(0);
  const [recordLoading, setRecordLoading] = useState(false);
  const [recordError, setRecordError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setLoadError('');
    listCouponActivities(query)
      .then((result) => {
        if (!active) return;
        setItems(result.Items);
        setTotal(result.Total);
      })
      .catch((error) => {
        if (active) setLoadError(errorMessage(error, '优惠券活动加载失败'));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [query, reload]);

  useEffect(() => {
    if (!recordActivity) return;
    let active = true;
    setRecordLoading(true);
    setRecordError('');
    listCouponRecords(recordActivity.ID, recordPage)
      .then((result) => {
        if (!active) return;
        setRecordItems(result.Items);
        setRecordTotal(result.Total);
      })
      .catch((error) => {
        if (active) setRecordError(errorMessage(error, '发放记录加载失败'));
      })
      .finally(() => {
        if (active) setRecordLoading(false);
      });
    return () => {
      active = false;
    };
  }, [recordActivity, recordPage]);

  function openEditor(item?: CouponActivity) {
    setSaveError('');
    edited.current = false;
    form.resetFields();
    if (item) {
      form.setFieldsValue({
        ...item,
        Description: item.Description || '',
        ApplicableScenes: item.ApplicableScenes?.length
          ? item.ApplicableScenes
          : [0],
        DisplayAmount:
          item.Amount /
          (item.CouponType === 1 ? 100 : item.CouponType === 2 ? 10 : 1),
        DisplayMinimum: item.MinimumAmount / (item.CouponType === 0 ? 1 : 100),
        Window: [dayjs(item.StartDate), dayjs(item.EndDate)],
        ExpireDays: item.Expire / DAY,
        CanReReceive: item.CanReReceive === 1,
      });
    } else {
      form.setFieldsValue({
        CouponType: 1,
        DisplayMinimum: 0,
        Count: 100,
        ExpireDays: 7,
        ApplicableScenes: [0],
        ControlRoles: [127],
        CanReReceive: false,
      });
    }
    setEditor(item || 'new');
  }

  function closeEditor() {
    if (savingRef.current) return;
    if (!edited.current) {
      setEditor(undefined);
      return;
    }
    Modal.confirm({
      className: 'oa-operation-modal',
      title: '放弃未保存的修改？',
      okText: '放弃修改',
      cancelText: '继续编辑',
      onOk: () => setEditor(undefined),
    });
  }

  async function submit(values: ActivityValues) {
    if (savingRef.current) return;
    savingRef.current = true;
    setSaving(true);
    setSaveError('');
    try {
      const kind = values.CouponType;
      await saveCouponActivity(editing?.ID, {
        Revision: editing?.Revision,
        Count: values.Count,
        ControlRoles: values.ControlRoles || [],
        ...(locked
          ? {}
          : {
              ActivityName: values.ActivityName,
              Title: values.Title,
              CouponType: kind,
              Amount:
                kind === 3
                  ? 0
                  : Math.round(
                      values.DisplayAmount *
                        (kind === 1 ? 100 : kind === 2 ? 10 : 1),
                    ),
              MinimumAmount: Math.round(
                values.DisplayMinimum * (kind === 0 ? 1 : 100),
              ),
              StartDate: values.Window[0].format('YYYY-MM-DD HH:mm:ss'),
              EndDate: values.Window[1].format('YYYY-MM-DD HH:mm:ss'),
              Expire:
                editing && !form.isFieldTouched('ExpireDays')
                  ? editing.Expire
                  : Math.round(values.ExpireDays * DAY),
              ApplicableScenes: kind === 0 ? [0] : values.ApplicableScenes,
              CanReReceive: values.CanReReceive ? 1 : 0,
              Description: values.Description || '',
            }),
      });
      message.success(editing ? '优惠券活动已更新' : '优惠券活动已创建');
      setEditor(undefined);
      setReload((value) => value + 1);
    } catch (error) {
      setSaveError(errorMessage(error, '保存失败，请重试'));
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  const columns: ColumnsType<CouponActivity> = [
    {
      title: '优惠券',
      width: 200,
      render: (_, item) => (
        <Space direction="vertical" size={2}>
          <Text strong>{item.Title}</Text>
          <Text type="secondary">{item.ActivityName}</Text>
          {item.SystemLocked && <Tag>邀请专用</Tag>}
        </Space>
      ),
    },
    {
      title: '使用规则',
      width: 155,
      render: (_, item) => (
        <Space direction="vertical" size={2}>
          <Text>{couponBenefit(item)}</Text>
          <Text type="secondary">
            {item.MinimumAmount
              ? `满 ${
                  item.CouponType === 0
                    ? `${item.MinimumAmount} 小时`
                    : currency(item.MinimumAmount)
                }`
              : '无门槛'}{' '}
            ·{' '}
            {(item.ApplicableScenes?.length ? item.ApplicableScenes : [0])
              .map((scene) => scenes[scene])
              .join(' / ')}
          </Text>
        </Space>
      ),
    },
    {
      title: '发放时间',
      width: 170,
      render: (_, item) => (
        <Space direction="vertical" size={2}>
          <Text>{dayjs(item.StartDate).format('YYYY-MM-DD HH:mm')}</Text>
          <Text type="secondary">
            至 {dayjs(item.EndDate).format('YYYY-MM-DD HH:mm')}
          </Text>
        </Space>
      ),
    },
    {
      title: '发券角色',
      width: 145,
      render: (_, item) =>
        item.ControlRoles?.map((role) => roles[role])
          .filter(Boolean)
          .join('、') || '未配置',
    },
    {
      title: '发放名额',
      width: 180,
      render: (_, item) => (
        <Space direction="vertical" size={2}>
          <Text strong>
            {item.Status === 'active' ? '可用' : '剩余'} {item.Available} /{' '}
            {item.Count}
          </Text>
          <Text type="secondary">
            已发 {item.Issued} · 预留 {item.Reserved} · 已用 {item.Used}
          </Text>
        </Space>
      ),
    },
    {
      title: '状态',
      width: 88,
      render: (_, item) => (
        <Tag color={item.Status === 'active' ? 'green' : undefined}>
          {statuses[item.Status]}
        </Tag>
      ),
    },
    {
      title: '操作',
      width: 136,
      render: (_, item) => (
        <Space>
          {!item.SystemLocked && (
            <Button type="link" size="small" onClick={() => openEditor(item)}>
              编辑
            </Button>
          )}
          <Button
            type="link"
            size="small"
            onClick={() => {
              setRecordPage(1);
              setRecordItems([]);
              setRecordTotal(0);
              setRecordActivity(item);
            }}
          >
            发放记录
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <PageContainer>
      <Card>
        <Space
          wrap
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginBottom: 16,
          }}
        >
          <Space wrap>
            <Input.Search
              aria-label="搜索优惠券"
              placeholder="券名称或活动名称"
              allowClear
              maxLength={30}
              onSearch={(Keyword) =>
                setQuery((previous) => ({
                  ...previous,
                  Keyword: Keyword.trim(),
                  Page: 1,
                }))
              }
            />
            <Select<ActivityStatus>
              aria-label="发放状态"
              placeholder="全部状态"
              allowClear
              style={{ width: 120 }}
              options={Object.entries(statuses).map(([value, label]) => ({
                value,
                label,
              }))}
              onChange={(Status) =>
                setQuery((previous) => ({ ...previous, Status, Page: 1 }))
              }
            />
          </Space>
          <Button type="primary" onClick={() => openEditor()}>
            新建优惠券
          </Button>
        </Space>
        {loadError && (
          <Alert
            type="error"
            showIcon
            message={loadError}
            style={{ marginBottom: 16 }}
            action={
              <Button
                size="small"
                onClick={() => setReload((value) => value + 1)}
              >
                重试
              </Button>
            }
          />
        )}
        <Table
          rowKey="ID"
          columns={columns}
          dataSource={items}
          loading={loading}
          scroll={{ x: 1075 }}
          locale={{ emptyText: '暂无符合条件的优惠券活动' }}
          pagination={{
            current: query.Page,
            total,
            pageSize: PAGE_SIZE,
            showSizeChanger: false,
            onChange: (Page) => setQuery((previous) => ({ ...previous, Page })),
          }}
        />
      </Card>

      <Drawer
        title={editing ? '编辑优惠券' : '新建优惠券'}
        width="min(100%, 560px)"
        open={!!editor}
        forceRender
        rootClassName="oa-operation-modal"
        onClose={closeEditor}
        closable={!saving}
        keyboard={!saving}
        maskClosable={!saving}
        footer={
          <Space>
            <Button
              type="primary"
              loading={saving}
              onClick={() => form.submit()}
            >
              保存优惠券
            </Button>
            <Button disabled={saving} onClick={closeEditor}>
              取消
            </Button>
          </Space>
        }
      >
        {locked && (
          <Alert
            message={editing?.Title}
            description="此券已有发放或抽奖预留，可继续调整总名额和发券角色。"
            type="info"
            showIcon
            style={{ marginBottom: 20 }}
          />
        )}
        {saveError && (
          <Alert
            type="error"
            showIcon
            message={saveError}
            style={{ marginBottom: 16 }}
          />
        )}
        <Form<ActivityValues>
          form={form}
          layout="vertical"
          disabled={saving}
          onFinish={submit}
          onValuesChange={() => {
            edited.current = true;
          }}
        >
          {!locked && (
            <>
              <Form.Item
                name="ActivityName"
                label="活动名称"
                rules={[{ required: true, whitespace: true }]}
              >
                <Input maxLength={30} placeholder="例如 周末福利抽奖" />
              </Form.Item>
              <Form.Item
                name="Title"
                label="券名称"
                rules={[{ required: true, whitespace: true }]}
              >
                <Input maxLength={30} placeholder="例如 10 元桌游抵扣券" />
              </Form.Item>
              <Row gutter={16}>
                <Col xs={24} sm={8}>
                  <Form.Item
                    name="CouponType"
                    label="券类型"
                    rules={[{ required: true }]}
                  >
                    <Select
                      options={numericOptions(types)}
                      onChange={(value) => {
                        form.setFieldsValue({
                          DisplayAmount: undefined,
                          DisplayMinimum: 0,
                          ...(value === 0 ? { ApplicableScenes: [0] } : {}),
                        });
                      }}
                    />
                  </Form.Item>
                </Col>
                {type !== 3 && (
                  <Col xs={24} sm={8}>
                    <Form.Item
                      name="DisplayAmount"
                      label={
                        type === 2
                          ? '折扣（折）'
                          : type === 0
                          ? '减免时长（小时）'
                          : '抵扣金额（元）'
                      }
                      rules={[{ required: true }]}
                    >
                      <InputNumber
                        style={{ width: '100%' }}
                        min={type === 0 ? 1 : type === 2 ? 0.1 : 0.01}
                        max={type === 2 ? 9.9 : undefined}
                        precision={type === 0 ? 0 : type === 2 ? 1 : 2}
                      />
                    </Form.Item>
                  </Col>
                )}
                <Col xs={24} sm={8}>
                  <Form.Item
                    name="DisplayMinimum"
                    label={type === 0 ? '门槛（小时）' : '门槛（元）'}
                    rules={[{ required: true }]}
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      min={0}
                      precision={type === 0 ? 0 : 2}
                    />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item
                name="ApplicableScenes"
                label="适用场景"
                rules={[{ required: true }]}
              >
                <Select
                  mode="multiple"
                  options={numericOptions(scenes)}
                  disabled={type === 0}
                />
              </Form.Item>
              <Form.Item
                name="Window"
                label="发放时间（北京时间）"
                rules={[{ required: true }]}
              >
                <DatePicker.RangePicker
                  showTime
                  format="YYYY-MM-DD HH:mm:ss"
                  style={{ width: '100%' }}
                />
              </Form.Item>
              <Form.Item
                name="ExpireDays"
                label="领取后有效期（天）"
                extra="0 表示领取当天有效。"
                rules={[{ required: true }]}
              >
                <InputNumber min={0} style={{ width: '100%' }} />
              </Form.Item>
            </>
          )}
          <Form.Item name="Count" label="总名额" rules={[{ required: true }]}>
            <InputNumber
              min={1}
              max={2147483647}
              precision={0}
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item
            name="ControlRoles"
            label="发券角色"
            extra="抽奖只能选本角色有权发放、且处于发放期的券。"
          >
            <Select
              mode="multiple"
              options={numericOptions(roles)}
              placeholder="选择可发放此券的角色"
            />
          </Form.Item>
          {!locked && (
            <>
              <Form.Item
                name="CanReReceive"
                label="不同分享可各领一张"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
              <Form.Item name="Description" label="内部备注（选填）">
                <Input.TextArea rows={2} maxLength={255} />
              </Form.Item>
            </>
          )}
        </Form>
      </Drawer>

      <Drawer
        title={
          recordActivity ? `${recordActivity.Title} · 发放记录` : '发放记录'
        }
        open={!!recordActivity}
        width="min(100%, 760px)"
        onClose={() => setRecordActivity(undefined)}
      >
        {recordError && (
          <Alert
            type="error"
            showIcon
            message={recordError}
            style={{ marginBottom: 16 }}
          />
        )}
        <Table<CouponRecord>
          rowKey="ID"
          dataSource={recordItems}
          loading={recordLoading}
          scroll={{ x: 640 }}
          locale={{ emptyText: '暂无发放记录' }}
          pagination={{
            current: recordPage,
            pageSize: PAGE_SIZE,
            total: recordTotal,
            showSizeChanger: false,
            onChange: setRecordPage,
          }}
          columns={[
            {
              title: '玩家',
              render: (_, item) =>
                item.NickName || (item.UserID ? `#${item.UserID}` : '—'),
            },
            { title: '来源', dataIndex: 'Source' },
            { title: '状态', dataIndex: 'Status' },
            { title: '到账时间', dataIndex: 'ReceivedAt' },
            {
              title: '到期时间',
              dataIndex: 'ExpireAt',
              render: (value) => value || '—',
            },
          ]}
        />
      </Drawer>
    </PageContainer>
  );
}
