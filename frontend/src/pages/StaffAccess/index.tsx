import { Table } from '@/components/AdaptiveTable';
import { PageContainer } from '@ant-design/pro-components';
import { request, useModel } from '@umijs/max';
import {
  Alert,
  Button,
  Checkbox,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Switch,
  Tabs,
  Tag,
  message,
} from 'antd';
import { useEffect, useState } from 'react';
interface Account {
  UserId: number;
  Name: string;
  Phone: string;
  Enabled: boolean;
  Headquarters: boolean;
  Verified: boolean;
  Grants: { StoreId: number; Role: string }[];
}
const base = '/admin_api/staff-access/v1';
async function api(path: string, method = 'GET', data?: unknown) {
  const r = await request<API.Response<any>>(base + path, { method, data });
  if (r.Code !== 0) throw Error('操作失败');
  return r.Data;
}
export default function StaffAccess() {
  const { initialState } = useModel('@@initialState');
  const stores = initialState?.auth?.Stores || [];
  const [accounts, setAccounts] = useState<Account[]>([]),
    [pages, setPages] = useState<any[]>([]),
    [roles, setRoles] = useState<Record<string, Record<string, boolean>>>({});
  const [audit, setAudit] = useState<any[]>([]),
    [total, setTotal] = useState(0),
    [auditPage, setAuditPage] = useState(1);
  const [editing, setEditing] = useState<number | null>(null),
    [open, setOpen] = useState(false),
    [saving, setSaving] = useState(false);
  const [candidates, setCandidates] = useState<any[]>([]),
    [keyword, setKeyword] = useState('');
  const [form] = Form.useForm();
  const load = async () => {
    const [a, p] = await Promise.all([api('/accounts'), api('/pages')]);
    setAccounts(a.Items);
    setPages(p.Pages);
    setRoles(p.Roles);
  };
  const loadAudit = async (page = 1) => {
    const r = await api('/audit?Page=' + page);
    setAudit(r.Items);
    setTotal(r.Total);
    setAuditPage(page);
  };
  useEffect(() => {
    load().catch(() => {});
    loadAudit().catch(() => {});
  }, []);
  const edit = (a?: Account) => {
    setEditing(a?.UserId ?? null);
    form.resetFields();
    form.setFieldsValue(
      a || { Enabled: true, Headquarters: false, Grants: [] },
    );
    setOpen(true);
  };
  const save = async () => {
    const v = await form.validateFields();
    setSaving(true);
    try {
      await api('/accounts/' + (editing ?? v.UserId), 'PUT', v);
      message.success('授权已保存，原有登录会话已撤销');
      setOpen(false);
      await load();
      await loadAudit();
    } finally {
      setSaving(false);
    }
  };
  const saveRole = async (role: string) => {
    setSaving(true);
    try {
      const values = Object.fromEntries(
        Object.entries(roles[role]).filter(
          ([k]) => pages.find((p) => p.id === k)?.scope !== 'admin',
        ),
      );
      await api('/pages/' + role, 'PUT', { Pages: values });
      message.success('页面授权已生效');
      await loadAudit();
    } finally {
      setSaving(false);
    }
  };
  return (
    <PageContainer
      title="员工及门店授权管理"
      subTitle="同一账号可在不同门店担任不同角色"
    >
      <Tabs
        items={[
          {
            key: 'accounts',
            label: '员工授权',
            children: (
              <>
                <Alert
                  type="info"
                  showIcon
                  message="门店授权按账号、门店和角色独立保存。停用或修改员工授权会撤销其现有 OA 会话。"
                  style={{ marginBottom: 16 }}
                />
                <Button
                  type="primary"
                  onClick={() => edit()}
                  style={{ marginBottom: 16 }}
                >
                  开通员工
                </Button>
                <Table
                  rowKey="UserId"
                  dataSource={accounts}
                  columns={[
                    {
                      title: '用户',
                      render: (_, a: Account) =>
                        `${a.Name || '未命名'} #${a.UserId}`,
                    },
                    { title: '登录手机号', dataIndex: 'Phone' },
                    {
                      title: '状态',
                      render: (_, a: Account) => (
                        <Space>
                          <Tag color={a.Enabled ? 'green' : 'default'}>
                            {a.Enabled ? '启用' : '停用'}
                          </Tag>
                        </Space>
                      ),
                    },
                    {
                      title: '授权范围',
                      render: (_, a: Account) =>
                        a.Headquarters ? (
                          <Tag color="purple">总部 · 全部门店</Tag>
                        ) : (
                          a.Grants.map((x) => (
                            <Tag key={x.StoreId}>
                              {stores.find((s) => s.Id === x.StoreId)?.Name ||
                                `门店 ${x.StoreId}`}{' '}
                              · {x.Role === 'manager' ? '店长' : '店员'}
                            </Tag>
                          ))
                        ),
                    },
                    {
                      title: '操作',
                      render: (_, a: Account) => (
                        <Button type="link" onClick={() => edit(a)}>
                          编辑授权
                        </Button>
                      ),
                    },
                  ]}
                />
              </>
            ),
          },
          {
            key: 'roles',
            label: '角色页面权限',
            children: (
              <>
                <Alert
                  type="info"
                  showIcon
                  message="可授权页面随菜单目录同步。新业务页默认开放给店长、对店员关闭；授权管理页始终仅总部可用。勾选页面包含页面内的业务操作，门店范围仍单独校验。"
                  style={{ marginBottom: 16 }}
                />
                <Table
                  rowKey="id"
                  pagination={false}
                  dataSource={pages}
                  columns={[
                    { title: '菜单页', dataIndex: 'name' },
                    {
                      title: '影响范围',
                      render: (_, p: any) =>
                        p.scope === 'global' ? (
                          <Tag color="orange">全品牌配置</Tag>
                        ) : p.scope === 'admin' ? (
                          <Tag color="purple">总部专属</Tag>
                        ) : (
                          '当前授权门店'
                        ),
                    },
                    ...['worker', 'manager'].map((role) => ({
                      title: role === 'worker' ? '店员' : '店长',
                      render: (_: unknown, p: any) => (
                        <Checkbox
                          disabled={p.scope === 'admin'}
                          checked={!!roles[role]?.[p.id]}
                          onChange={(e) =>
                            setRoles({
                              ...roles,
                              [role]: {
                                ...roles[role],
                                [p.id]: e.target.checked,
                              },
                            })
                          }
                        />
                      ),
                    })),
                  ]}
                />
                <Space style={{ marginTop: 16 }}>
                  <Button loading={saving} onClick={() => saveRole('worker')}>
                    保存店员权限
                  </Button>
                  <Button
                    type="primary"
                    loading={saving}
                    onClick={() => saveRole('manager')}
                  >
                    保存店长权限
                  </Button>
                </Space>
              </>
            ),
          },
          {
            key: 'audit',
            label: '操作审计',
            children: (
              <Table
                rowKey="Id"
                dataSource={audit}
                pagination={{
                  current: auditPage,
                  total,
                  pageSize: 50,
                  onChange: loadAudit,
                }}
                expandable={{
                  expandedRowRender: (r) => (
                    <pre style={{ whiteSpace: 'pre-wrap' }}>
                      {JSON.stringify(r.Detail, null, 2)}
                    </pre>
                  ),
                }}
                columns={[
                  { title: '时间', dataIndex: 'Time' },
                  { title: '操作人 ID', dataIndex: 'ActorId' },
                  { title: '门店', dataIndex: 'StoreId' },
                  { title: '操作', dataIndex: 'Action' },
                  { title: '对象', dataIndex: 'Target' },
                ]}
              />
            ),
          },
        ]}
      />
      <Modal
        title={editing ? '编辑员工授权' : '开通员工'}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => save().catch(() => {})}
        confirmLoading={saving}
        width={680}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          {!editing && (
            <>
              <Space.Compact block style={{ marginBottom: 12 }}>
                <Input
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  placeholder="按用户 ID、昵称或完整手机号查找"
                />
                <Button
                  onClick={async () =>
                    setCandidates(
                      (
                        await api(
                          '/candidates?Keyword=' + encodeURIComponent(keyword),
                        )
                      ).Items,
                    )
                  }
                >
                  查找用户
                </Button>
              </Space.Compact>
              <Form.Item
                name="UserId"
                label="关联小程序用户"
                rules={[{ required: true }]}
              >
                <Select
                  options={candidates.map((c) => ({
                    value: c.UserId,
                    label: `${c.Name || '未命名'} #${c.UserId}`,
                  }))}
                />
              </Form.Item>
            </>
          )}
          <Form.Item
            name="PhoneNumber"
            label={editing ? '更换登录手机号（留空保持原绑定）' : '登录手机号'}
            rules={[
              {
                required: !editing,
                pattern: /^1[3-9]\d{9}$/,
                message: '请输入正确的手机号',
              },
            ]}
          >
            <Input autoComplete="off" maxLength={11} />
          </Form.Item>
          <Form.Item
            name="Enabled"
            label="启用员工身份"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
          <Form.Item
            name="Headquarters"
            label="总部管理员（全部门店与授权管理）"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
          <Form.List name="Grants">
            {(fields, { add, remove }) => (
              <>
                <p>门店角色</p>
                {fields.map(({ key, name, ...rest }) => (
                  <Space key={key} align="baseline">
                    <Form.Item
                      {...rest}
                      name={[name, 'StoreId']}
                      rules={[{ required: true }]}
                    >
                      <Select
                        placeholder="选择门店"
                        style={{ width: 250 }}
                        options={stores.map((s) => ({
                          value: s.Id,
                          label: s.Name,
                        }))}
                      />
                    </Form.Item>
                    <Form.Item
                      {...rest}
                      name={[name, 'Role']}
                      rules={[{ required: true }]}
                    >
                      <Select
                        style={{ width: 130 }}
                        options={[
                          { label: '店员', value: 'worker' },
                          { label: '店长', value: 'manager' },
                        ]}
                      />
                    </Form.Item>
                    <Button onClick={() => remove(name)}>移除</Button>
                  </Space>
                ))}
                <Button
                  block
                  type="dashed"
                  onClick={() => add({ Role: 'worker' })}
                >
                  添加门店授权
                </Button>
              </>
            )}
          </Form.List>
          <Alert
            type="warning"
            showIcon
            style={{ marginTop: 16 }}
            message="请核实用户与手机号归属"
            description="此操作授予员工能力，不会合并或迁移顾客的储值、积分、月卡。"
          />
        </Form>
      </Modal>
    </PageContainer>
  );
}
