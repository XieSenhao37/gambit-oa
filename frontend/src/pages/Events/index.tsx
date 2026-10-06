import { Table } from '@/components/AdaptiveTable';
import { getCurrentStoreId } from '@/components/StoreSwitcher';
import { eventAPI } from '@/services/event';
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
  Statistic,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import dayjs from 'dayjs';
import { useEffect, useRef, useState } from 'react';
const { Text } = Typography;
export default function Events() {
  const [projects, setProjects] = useState<any[]>([]),
    [project, setProject] = useState<number>(),
    [store] = useState(getCurrentStoreId()),
    [month, setMonth] = useState(dayjs()),
    [tab, setTab] = useState('dashboard');
  const [data, setData] = useState<any>(),
    [events, setEvents] = useState<any[]>([]),
    [decks, setDecks] = useState<any[]>([]),
    [claims, setClaims] = useState<any[]>([]),
    [detail, setDetail] = useState<any>(),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const [edit, setEdit] = useState<any>(),
    [config, setConfig] = useState<any>(),
    [saving, setSaving] = useState(false);
  const [form] = Form.useForm(),
    [cfgForm] = Form.useForm();
  const generation = useRef(0);
  const [newDeckName, setNewDeckName] = useState('');
  const [addingDeck, setAddingDeck] = useState(false);
  const addingDeckRef = useRef(false);
  const editRef = useRef<any>();
  editRef.current = edit;
  const addDeck = async () => {
    const name = newDeckName.trim();
    const projectID = detail?.Event?.project_id;
    const participantID = edit?.id;
    if (!name || !projectID || addingDeckRef.current) return;
    addingDeckRef.current = true;
    setAddingDeck(true);
    try {
      const existing = decks.find(
        (d) => d.name.toLowerCase() === name.toLowerCase(),
      );
      if (existing) {
        if (!existing.status) {
          message.warning('该卡组已停用');
          return;
        }
        form.setFieldValue('deck_id', existing.id);
        setNewDeckName('');
        return;
      }
      await eventAPI('decks', 'POST', {
        project_id: projectID,
        name,
        status: 1,
        sort: 0,
      });
      const result = await eventAPI('decks', 'GET', { project_id: projectID });
      if (editRef.current?.id !== participantID) return;
      setDecks(result.Items);
      const created = result.Items.find((d: any) => d.name === name);
      if (created) form.setFieldValue('deck_id', created.id);
      setNewDeckName('');
      message.success('卡组已添加并选中');
    } catch (e: any) {
      message.error(e.message || '添加失败，请重试');
    } finally {
      addingDeckRef.current = false;
      setAddingDeck(false);
    }
  };
  const loadProjects = async () => {
    const d = await eventAPI('projects');
    setProjects(d.Items);
    setProject((p) => p || d.Items[0]?.id);
  };
  useEffect(() => {
    loadProjects().catch((e) => message.error(e.message));
  }, []);
  const load = async () => {
    if (!project) return;
    const gen = ++generation.current;
    setBusy(true);
    setError('');
    try {
      const params = {
        project_id: project,
        store_id: store,
        month: month.format('YYYY-MM'),
      };
      const [d, e, c, k] = await Promise.all([
        eventAPI('dashboard', 'GET', params),
        eventAPI('events', 'GET', params),
        eventAPI('claims', 'GET', params),
        eventAPI('decks', 'GET', { project_id: project }),
      ]);
      if (gen === generation.current) {
        setData(d);
        setEvents(e.Items);
        setClaims(c.Items);
        setDecks(k.Items);
      }
    } catch (e: any) {
      if (gen === generation.current) {
        setError(e.message);
        setData(undefined);
        setEvents([]);
      }
    } finally {
      if (gen === generation.current) setBusy(false);
    }
  };
  useEffect(() => {
    setDetail(undefined);
    load();
    return () => {
      generation.current++;
    };
  }, [project, store, month]);
  const openEvent = async (id: number) => {
    try {
      setDetail(await eventAPI('events/' + id));
    } catch (e: any) {
      message.error(e.message);
    }
  };
  const openConfig = (kind: string, row?: any) => {
    setConfig({ kind, row });
    cfgForm.setFieldsValue(row || { name: '', status: 1, sort: 0 });
  };
  const identity = [
    { title: '玩家编号', dataIndex: 'user_id' },
    { title: '昵称', dataIndex: 'nick_name' },
    { title: '卡牌 ID', dataIndex: 'card_id' },
  ];
  const eventColumns = [
    {
      title: '赛事 ID',
      dataIndex: 'code',
      render: (v: string, r: any) => (
        <Button type="link" onClick={() => openEvent(r.id)}>
          {v}
        </Button>
      ),
    },
    { title: '门店', dataIndex: 'store_name' },
    {
      title: '比赛时间',
      dataIndex: 'started_at',
      render: (v: string) => v || '尚无人签到',
    },
    {
      title: '人数',
      dataIndex: 'participants',
      sorter: (a: any, b: any) => a.participants - b.participants,
    },
    { title: '签到积分', dataIndex: 'points' },
    {
      title: '状态',
      dataIndex: 'status',
      render: (v: string) => <Tag>{v === 'ended' ? '已结束' : '可签到'}</Tag>,
    },
  ];
  const configColumns = [
    { title: '名称', dataIndex: 'name' },
    { title: '排序', dataIndex: 'sort' },
    {
      title: '状态',
      dataIndex: 'status',
      render: (v: number) => (v ? '启用' : '停用'),
    },
    {
      title: '操作',
      render: (_: any, r: any) => (
        <Button type="link" onClick={() => openConfig('decks', r)}>
          编辑
        </Button>
      ),
    },
  ];
  const metrics = data?.Metrics || {};
  return (
    <PageContainer title="赛事大盘">
      <Space wrap style={{ marginBottom: 20 }}>
        <Select
          style={{ width: 160 }}
          placeholder="选择项目"
          value={project}
          options={projects.map((p) => ({
            label: p.name + (p.status ? '' : '（停用）'),
            value: p.id,
          }))}
          onChange={setProject}
        />
        <DatePicker
          picker="month"
          allowClear={false}
          value={month}
          onChange={(v) => v && setMonth(v)}
        />
        <Button loading={busy} onClick={load}>
          刷新
        </Button>
      </Space>
      {error && (
        <Card>
          <Text type="danger">{error}</Text>
        </Card>
      )}
      <Tabs
        activeKey={tab}
        onChange={setTab}
        items={[
          {
            key: 'dashboard',
            label: '赛事看板',
            children: (
              <>
                <Row gutter={[16, 16]}>
                  {[
                    ['本月场次数', 'events'],
                    ['MAU（参赛人次）', 'mau'],
                    ['去重玩家数', 'uu'],
                    ['连续 UU', 'continuous_uu'],
                    ['新参赛玩家', 'new_players'],
                    ['回归率 %', 'return_rate'],
                    ['人均参赛场次', 'events_per_player'],
                  ].map(([name, key]) => (
                    <Col key={key} xs={12} lg={6}>
                      <Card>
                        <Statistic title={name} value={metrics[key] ?? '—'} />
                      </Card>
                    </Col>
                  ))}
                </Row>
                <Card style={{ marginTop: 16 }}>
                  <Text type="secondary">
                    MAU 按参赛人次累加；连续 UU
                    为相邻两个月均参赛的玩家；回归率＝连续
                    UU／上月去重玩家数。场次按首位成功签到时间归属月份，空赛事不计入。
                  </Text>
                </Card>
                <Card
                  title="赛事人数排名 · 点击人数列可切换最多 / 最少"
                  style={{ marginTop: 16 }}
                >
                  <Table
                    loading={busy}
                    rowKey="id"
                    dataSource={data?.EventRanking || []}
                    columns={eventColumns.slice(0, 4)}
                    scroll={{ x: 700 }}
                  />
                </Card>
                <Card
                  title="活跃玩家 · 当月参赛场次数"
                  style={{ marginTop: 16 }}
                >
                  <Table
                    rowKey="user_id"
                    dataSource={data?.ActivePlayers || []}
                    columns={[
                      ...identity,
                      {
                        title: '参赛场次',
                        dataIndex: 'events',
                        sorter: (a: any, b: any) => a.events - b.events,
                      },
                      { title: '最近参赛', dataIndex: 'last_event_at' },
                    ]}
                  />
                </Card>
                <Card
                  title="待召回玩家 · 上月来过，本月未参赛"
                  style={{ marginTop: 16 }}
                >
                  <Table
                    rowKey="user_id"
                    dataSource={data?.RecallPlayers || []}
                    columns={[
                      ...identity,
                      {
                        title: '联系电话',
                        dataIndex: 'phone',
                        render: (v: string) => (
                          <Text copyable={!!v}>{v || '未提供'}</Text>
                        ),
                      },
                      { title: '上月场次', dataIndex: 'previous_events' },
                      { title: '最近参赛', dataIndex: 'last_event_at' },
                    ]}
                    scroll={{ x: 850 }}
                  />
                </Card>
                <Card title="卡组使用分布" style={{ marginTop: 16 }}>
                  <Table
                    rowKey="name"
                    dataSource={data?.Decks || []}
                    scroll={{ x: 800 }}
                    columns={[
                      { title: '卡组', dataIndex: 'name' },
                      {
                        title: '使用人次',
                        dataIndex: 'count',
                        sorter: (a: any, b: any) => a.count - b.count,
                      },
                      {
                        title: '冠军人次',
                        dataIndex: 'champions',
                        sorter: (a: any, b: any) => a.champions - b.champions,
                      },
                      {
                        title: '亚军人次',
                        dataIndex: 'runners_up',
                        sorter: (a: any, b: any) => a.runners_up - b.runners_up,
                      },
                      {
                        title: '4强人次',
                        dataIndex: 'top_four',
                        sorter: (a: any, b: any) => a.top_four - b.top_four,
                      },
                      {
                        title: '8强人次',
                        dataIndex: 'top_eight',
                        sorter: (a: any, b: any) => a.top_eight - b.top_eight,
                      },
                    ]}
                  />
                </Card>
              </>
            ),
          },
          {
            key: 'events',
            label: '赛事记录',
            children: (
              <Card>
                <Table
                  rowKey="id"
                  loading={busy}
                  dataSource={events}
                  columns={eventColumns}
                  scroll={{ x: 950 }}
                />
              </Card>
            ),
          },
          {
            key: 'claims',
            label: '任务核销记录',
            children: (
              <Card>
                <Table
                  rowKey="id"
                  dataSource={claims}
                  columns={[
                    { title: '玩家编号', dataIndex: 'user_id' },
                    { title: '昵称', dataIndex: 'nick_name' },
                    { title: '积分', dataIndex: 'points' },
                    { title: '核销人', dataIndex: 'verifier' },
                    { title: '核销门店', dataIndex: 'store_name' },
                    { title: '核销时间', dataIndex: 'verified_at' },
                  ]}
                />
              </Card>
            ),
          },
          {
            key: 'config',
            label: '项目配置',
            children: (
              <>
                <Alert
                  style={{ marginBottom: 16 }}
                  type="warning"
                  showIcon
                  message="项目及卡组配置为全品牌共用，修改会影响所有门店。赛事经营数据仍按当前门店查看。"
                />
                <Card
                  title="项目（同步到小程序赛事与我的卡牌 ID）"
                  extra={
                    <Button onClick={() => openConfig('projects')}>
                      新增项目
                    </Button>
                  }
                >
                  <Table
                    rowKey="id"
                    dataSource={projects}
                    columns={[
                      ...configColumns.slice(0, 3),
                      {
                        title: '操作',
                        render: (_: any, r: any) => (
                          <Button
                            type="link"
                            onClick={() => openConfig('projects', r)}
                          >
                            编辑
                          </Button>
                        ),
                      },
                    ]}
                  />
                </Card>
              </>
            ),
          },
        ]}
      />
      <Drawer
        width={1000}
        open={!!detail}
        onClose={() => setDetail(undefined)}
        title={
          detail ? `${detail.Event.project_name} · ${detail.Event.code}` : ''
        }
      >
        <Text type="secondary">
          签到 ID 为当次参赛快照；修改名次与卡组不会自动发放积分。允许并列名次。
        </Text>
        <Table
          rowKey="id"
          dataSource={detail?.Items || []}
          columns={[
            ...identity,
            { title: '电话', dataIndex: 'phone' },
            { title: '签到时间', dataIndex: 'created_at' },
            { title: '名次', dataIndex: 'rank' },
            { title: '卡组', dataIndex: 'deck_name' },
            {
              title: '操作',
              render: (_: any, r: any) => (
                <Button
                  type="link"
                  onClick={() => {
                    setEdit(r);
                    setNewDeckName('');
                    form.setFieldsValue({ rank: r.rank, deck_id: r.deck_id });
                  }}
                >
                  编辑
                </Button>
              ),
            },
          ]}
          scroll={{ x: 950 }}
        />
      </Drawer>
      <Modal
        title="参赛名次与卡组"
        open={!!edit}
        confirmLoading={saving}
        okButtonProps={{ disabled: addingDeck }}
        onCancel={() => setEdit(undefined)}
        onOk={async () => {
          try {
            const v = await form.validateFields();
            setSaving(true);
            await eventAPI('participants/' + edit.id, 'PUT', v);
            setEdit(undefined);
            await openEvent(detail.Event.id);
            await load();
            message.success('已保存');
          } catch (e: any) {
            if (e.message) message.error(e.message);
          } finally {
            setSaving(false);
          }
        }}
      >
        <Form
          form={form}
          layout="horizontal"
          labelCol={{ flex: '120px' }}
          wrapperCol={{ flex: 1 }}
          labelAlign="left"
          style={{ marginTop: 24 }}
        >
          <Form.Item name="rank" label="名次（可留空）">
            <InputNumber
              min={1}
              max={100000}
              precision={0}
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item name="deck_id" label="卡组">
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              placeholder="选择或添加卡组"
              dropdownRender={(menu) => (
                <>
                  {menu}
                  <div
                    style={{
                      borderTop: '1px solid #f0f0f0',
                      padding: '10px 8px 4px',
                      display: 'flex',
                      gap: 8,
                    }}
                  >
                    <Input
                      placeholder="输入新卡组名称"
                      maxLength={60}
                      value={newDeckName}
                      disabled={addingDeck}
                      onChange={(e) => setNewDeckName(e.target.value)}
                      onKeyDown={(e) => e.stopPropagation()}
                      onPressEnter={() => addDeck()}
                    />
                    <Button
                      type="primary"
                      loading={addingDeck}
                      disabled={!newDeckName.trim()}
                      onClick={addDeck}
                    >
                      添加
                    </Button>
                  </div>
                </>
              )}
              options={decks
                .filter((d) => d.status || d.id === edit?.deck_id)
                .map((d) => ({ label: d.name, value: d.id }))}
            />
          </Form.Item>
        </Form>
      </Modal>
      <Modal
        title={config?.kind === 'projects' ? '项目配置' : '卡组配置'}
        open={!!config}
        confirmLoading={saving}
        onCancel={() => setConfig(undefined)}
        onOk={async () => {
          try {
            const v = await cfgForm.validateFields();
            setSaving(true);
            await eventAPI(
              config.kind + (config.row ? '/' + config.row.id : ''),
              config.row ? 'PUT' : 'POST',
              { ...v, project_id: project },
            );
            setConfig(undefined);
            await loadProjects();
            await load();
            message.success('已保存');
          } catch (e: any) {
            if (e.message) message.error(e.message);
          } finally {
            setSaving(false);
          }
        }}
      >
        <Form form={cfgForm} layout="vertical">
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, whitespace: true, max: 60 }]}
          >
            <Input maxLength={60} />
          </Form.Item>
          <Form.Item name="sort" label="排序">
            <InputNumber min={0} max={10000} precision={0} />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select
              options={[
                { value: 1, label: '启用' },
                { value: 0, label: '停用' },
              ]}
            />
          </Form.Item>
          <Text type="secondary">
            停用保留历史记录，新签到和任务不再使用停用的项目。
          </Text>
        </Form>
      </Modal>
    </PageContainer>
  );
}
