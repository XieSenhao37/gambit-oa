import { Table } from '@/components/AdaptiveTable';
import { getMonthCardConfig, manualOpenMonthCards } from '@/services/monthCard';
import { createRequestKey } from '@/utils/requestKey';
import { PageContainer } from '@ant-design/pro-components';
import { useModel } from '@umijs/max';
import {
  Alert,
  Button,
  Card,
  Descriptions,
  InputNumber,
  Modal,
  Space,
  Typography,
} from 'antd';
import dayjs from 'dayjs';
import { useEffect, useRef, useState } from 'react';
import UserPicker from './UserPicker';

type Pending = {
  Users: API.UserInfo[];
  OpenMonths: number;
  ExpectedPrice: number;
  RequestKey: string;
};
function restore(key: string): Pending | undefined {
  try {
    const saved = JSON.parse(sessionStorage.getItem(key) || 'null');
    return saved?.Users?.length && saved?.RequestKey ? saved : undefined;
  } catch {
    return undefined;
  }
}
export default function MonthCardOpen() {
  const { initialState } = useModel('@@initialState');
  const storageKey = `month-card-pending-${initialState?.auth?.UserId}`;
  const [pending, setPending] = useState<Pending | undefined>(() =>
    restore(storageKey),
  );
  const [users, setUsers] = useState<API.UserInfo[]>(pending?.Users || []);
  const [months, setMonths] = useState(pending?.OpenMonths || 1);
  const [price, setPrice] = useState<number | undefined>(
    pending?.ExpectedPrice,
  );
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  const [picker, setPicker] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [result, setResult] = useState<API.MonthCardOrderItem[]>([]);
  const [reload, setReload] = useState(0);
  const inFlight = useRef(false);
  useEffect(() => {
    if (pending) return;
    let active = true;
    setPrice(undefined);
    setLoading(true);
    getMonthCardConfig()
      .then((response) => {
        if (!active) return;
        if (response.Code !== 0 || !response.Data)
          throw new Error(response.Message || '月卡价格读取失败');
        setPrice(response.Data.Price);
      })
      .catch((err) => {
        if (active)
          setError(
            err?.response?.data?.Message ||
              (err?.response || err?.request ? undefined : err.message) ||
              '月卡价格读取失败，请重试',
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [reload, !!pending]);
  const locked = saving || !!pending;
  const clearPending = () => {
    sessionStorage.removeItem(storageKey);
    setPending(undefined);
  };
  const submit = async () => {
    if (inFlight.current || price === undefined || !users.length) return;
    inFlight.current = true;
    setSaving(true);
    setError(undefined);
    try {
      const submission = pending || {
        Users: users,
        OpenMonths: months,
        ExpectedPrice: price,
        RequestKey: createRequestKey(),
      };
      // Persist before sending, so refreshing after a timeout can retry the same batch.
      sessionStorage.setItem(storageKey, JSON.stringify(submission));
      setPending(submission);
      const response = await manualOpenMonthCards({
        UserIds: submission.Users.map((user) => user.Id),
        OpenMonths: submission.OpenMonths,
        ExpectedPrice: submission.ExpectedPrice,
        RequestKey: submission.RequestKey,
      });
      if (response.Code !== 0 || !response.Data)
        throw new Error(response.Message || '开通结果未确认，请重试');
      setResult(response.Data.Items);
      setUsers([]);
      setConfirm(false);
      clearPending();
    } catch (err: any) {
      const status = err?.response?.status;
      if (status === 400 || status === 401 || status === 403) clearPending();
      setError(
        err?.response?.data?.Message ||
          (err?.response || err?.request ? undefined : err.message) ||
          '开通结果未确认，请使用同一请求重试',
      );
    } finally {
      inFlight.current = false;
      setSaving(false);
    }
  };
  return (
    <PageContainer>
      <Card style={{ maxWidth: 960 }}>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Alert
            showIcon
            message="本入口由总部承担月卡费用，按当前配置价参与门店结算，不计现金收入。"
          />
          <Space>
            <Typography.Text strong>开通用户（{users.length}）</Typography.Text>
            <Button onClick={() => setPicker(true)} disabled={locked}>
              选择用户
            </Button>
          </Space>
          <Table<API.UserInfo>
            rowKey="Id"
            dataSource={users}
            locale={{ emptyText: '请先选择需要开通月卡的用户' }}
            pagination={
              users.length > 10
                ? { pageSize: 10, showSizeChanger: false }
                : false
            }
            columns={[
              { title: '用户ID', dataIndex: 'Id', width: 90 },
              {
                title: '昵称',
                dataIndex: 'NickName',
                width: 180,
                render: (value) => value || '未设置昵称',
              },
              {
                title: '手机号',
                dataIndex: 'PhoneNumber',
                width: 150,
                render: (value) => value || '未绑定',
              },
              {
                title: '当前月卡到期',
                dataIndex: 'MonthCardExpire',
                width: 180,
                render: (value) => value || '尚未开通',
              },
              {
                title: '操作',
                width: 70,
                render: (_, row) => (
                  <Button
                    type="link"
                    disabled={locked}
                    onClick={() =>
                      setUsers((previous) =>
                        previous.filter((user) => user.Id !== row.Id),
                      )
                    }
                  >
                    移除
                  </Button>
                ),
              },
            ]}
          />
          <Descriptions column={1} size="small">
            <Descriptions.Item label="开通期数">
              <InputNumber
                aria-label="开通期数"
                min={1}
                max={12}
                precision={0}
                value={months}
                disabled={locked}
                onChange={(value) => setMonths(value || 1)}
              />
              <span style={{ marginLeft: 8 }}>
                每期 30 天，每人共 {months * 30} 天
              </span>
            </Descriptions.Item>
          </Descriptions>
          <Typography.Text type="secondary">
            尚未开通或已过期的月卡立即生效；有效月卡从原到期时间顺延。所选用户使用相同期数，整批开通成功才保存。
          </Typography.Text>
          {pending && !saving && (
            <Alert
              showIcon
              type="warning"
              message="上次开通结果尚未确认，请重试以核对结果。核对完成前保留原用户和期数，重试不会重复开通。"
            />
          )}
          {error && (
            <Alert
              showIcon
              type="error"
              message={error}
              action={
                price === undefined && !locked ? (
                  <Button
                    loading={loading}
                    onClick={() => {
                      setError(undefined);
                      setReload((value) => value + 1);
                    }}
                  >
                    重试
                  </Button>
                ) : undefined
              }
            />
          )}
          <Button
            type="primary"
            loading={saving}
            disabled={!users.length || price === undefined || loading}
            onClick={() => setConfirm(true)}
          >
            {pending ? '重试开通' : '开通月卡'}
          </Button>
          {!!result.length && (
            <>
              <Alert
                showIcon
                type="success"
                message={`已成功为 ${result.length} 位用户开通月卡`}
              />
              <Table<API.MonthCardOrderItem>
                rowKey="Id"
                dataSource={result}
                pagination={{ pageSize: 10, showSizeChanger: false }}
                columns={[
                  { title: '用户ID', dataIndex: 'UserId', width: 90 },
                  {
                    title: '昵称',
                    dataIndex: 'NickName',
                    width: 180,
                    render: (value) => value || '未设置昵称',
                  },
                  {
                    title: '本次开通后到期',
                    width: 180,
                    render: (_, row) =>
                      row.EffectiveAt
                        ? dayjs(row.EffectiveAt)
                            .add(row.DurationDays, 'day')
                            .format('YYYY-MM-DD HH:mm:ss')
                        : '—',
                  },
                ]}
              />
            </>
          )}
        </Space>
      </Card>
      <UserPicker
        open={picker}
        value={users}
        onCancel={() => setPicker(false)}
        onConfirm={(selected) => {
          setUsers(selected);
          setPicker(false);
          setResult([]);
          setError(undefined);
        }}
      />
      <Modal
        title="确认开通月卡"
        open={confirm}
        okText={pending ? '重试并核对' : '确认开通'}
        cancelText="取消"
        confirmLoading={saving}
        cancelButtonProps={{ disabled: saving }}
        closable={!saving}
        keyboard={!saving}
        maskClosable={false}
        onCancel={() => {
          if (!inFlight.current) setConfirm(false);
        }}
        onOk={submit}
      >
        {error && (
          <Alert
            showIcon
            type="error"
            message={error}
            style={{ marginBottom: 16 }}
          />
        )}
        <p>
          为 {users.length} 位用户每人开通 {months} 期（{months * 30} 天）月卡。
        </p>
      </Modal>
    </PageContainer>
  );
}
